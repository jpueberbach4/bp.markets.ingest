import os, time, torch, threading
from datetime import datetime
from ingest import IndicatorIngestor
from reactor import PersistentReactor, log_queue, async_sink_worker 
from config import CONFIG

DEVICE = torch.device("cuda")

def run():
    sink_thread = threading.Thread(target=async_sink_worker, daemon=True)
    sink_thread.start()

    os.makedirs("checkpoints", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    if not os.path.exists(CONFIG['LOG_FILE']):
        with open(CONFIG['LOG_FILE'], "w") as f: 
            f.write("timestamp,gen,f1,prec,rec,sigs,genes\n")

    ingestor = IndicatorIngestor(CONFIG)
    feats, targets, _ = ingestor.get_data() 

    reactor = PersistentReactor(feats, targets, CONFIG, DEVICE)
    
    start_gen = 0
    best_ever = 0.0
    
    # --- MULTI-DAY RESUME LOGIC ---
    pop_ckpt_path = "checkpoints/population_latest.pt"
    if os.path.exists(pop_ckpt_path):
        print(f"\n🔄 [SYSTEM] Restoring population ecosystem from {pop_ckpt_path}...")
        start_gen, best_ever = reactor.load_checkpoint(pop_ckpt_path)

    print("\n" + "="*85)
    print(f"{'GEN':<6} | {'F1':<8} | {'PREC':<8} | {'REC':<8} | {'SIGS':<6} | {'FPS':<6}")
    print("-" * 85)

    try:
        for gen in range(start_gen, 1000000):
            t0 = time.time()
            
            metrics = reactor.run_generation()
            
            if len(metrics['f1']) == 0:
                print(f"⚠️ GEN {gen} produced no results.")
                continue

            f1_scores = metrics["f1"]
            best_idx = torch.argmax(f1_scores)
            best_val = f1_scores[best_idx].item()
            
            max_sigs = int(metrics['sigs'].max().item())
            avg_f1 = f1_scores.mean().item()
            
            cur_p = metrics["prec"][best_idx].item()
            cur_r = metrics["rec"][best_idx].item()
            cur_s = metrics["sigs"][best_idx].item()
            
            fps = CONFIG["POP_SIZE"] / (time.time() - t0)

            if best_val > best_ever:
                best_ever = best_val
                gn = [reactor.unique_inds[i] for i in reactor.population[best_idx]]
                
                print(f"\n🌟 {gen:<4} | {best_ever:.4f} | {cur_p:.4f} | {cur_r:.4f} | {int(cur_s):<6} | {fps:.1f}")
                print(f"   └─ Genes: {gn}")
                
                scan_threshold = CONFIG.get('ATOMIC_SCAN_THRESHOLD', 0.5)
                if best_ever > scan_threshold:
                    scan_size = CONFIG.get('ATOMIC_SCAN_SIZE', 6)
                    vitality_pool = CONFIG.get('ATOMIC_VITALITY_POOL', 40)
                    print(f"   🔬 Triggering Atomic {scan_size}-Gene Scan for Ground Truth...")
                    reactor.run_atomic_scan(top_n_vitality=vitality_pool, scan_size=scan_size)
                
                log_entry = f"{datetime.now()},{gen},{best_ever:.4f},{cur_p:.4f},{cur_r:.4f},{cur_s},{'|'.join(gn)}"
                log_queue.put((CONFIG['LOG_FILE'], log_entry, False))
                torch.cuda.synchronize()
                
                best_model = {
                    'gen': gen, 'f1': best_ever, 'genes': gn, 
                    'state_dict': {
                        'W1': reactor.pop_W1[best_idx].cpu(), 'W2': reactor.pop_W2[best_idx].cpu(),
                        'B1': reactor.pop_B1[best_idx].cpu(), 'B2': reactor.pop_B2[best_idx].cpu(),
                        'threshold': reactor.thresholds[best_idx].cpu()
                    }
                }
                log_queue.put((f"best_model_gen_{gen}.pt", best_model, True))
            else:
                print(f"🚜 {gen:<4} | Best: {best_ever:.4f} | Avg: {avg_f1:.4f} | MaxSig: {max_sigs:<4} | FPS: {fps:.1f}")

            # --- POPULATION CHECKPOINTING (Offloaded to Sink) ---
            pop_state = {
                'gen': gen + 1, 'best_ever': best_ever,
                'population': reactor.population.cpu(),
                'W1': reactor.pop_W1.cpu(), 'W2': reactor.pop_W2.cpu(),
                'B1': reactor.pop_B1.cpu(), 'B2': reactor.pop_B2.cpu(),
                'thresholds': reactor.thresholds.cpu(),
                'gene_scores': reactor.gene_scores.cpu(),
                'gene_usage': reactor.gene_usage.cpu()
            }
            log_queue.put(("population_latest.pt", pop_state, True))

            reactor.evolve(f1_scores.to(DEVICE))

    except KeyboardInterrupt:
        print("\n[!] Shutdown Signal Received. Cleaning up...")
        log_queue.put(None)
        sink_thread.join(timeout=5) 
        print("Reactor Off. Fly safe.")

if __name__ == "__main__":
    run()