import os, time, torch, threading
from datetime import datetime
from ingest import IndicatorIngestor
from reactor import PersistentReactor, log_queue, async_sink_worker 

# CONFIGURATION
BLACKLISTED_INDICATORS = [
    # Original
    'zigzag*', 'swing-points*', 'fractaldimension*', 'kalman*', 
    'open', 'high', 'low', 'close', 'volume', 
    'is-open*', 'pivot*', 'camarilla-pivots*', 'psychlevels*', 
    'sma*', 'midpoint*', 'drift*', 
    "*example-pivot-finder*", "*elliot*", "*macro*", "*fibonacci*", "feature*",

    # MATH JUNK (Trig, logs, and arithmetic used for curve fitting)
    'talib-cos*', 'talib-sin*', 'talib-tan*', 'talib-acos*', 'talib-asin*', 
    'talib-atan*', 'talib-mult*', 'talib-div*', 'talib-add*', 'talib-sub*', 
    'talib-sqrt*', 'talib-exp*', 'talib-ceil*', 'talib-floor*', 'talib-cosh*', 
    'talib-sinh*', 'talib-tanh*', 'talib-ln*', 'talib-log10*', 'talib-sqrt*',

    # CYCLES & SIGNAL PROCESSING (The GA uses these to find "phantom" cycles)
    'talib-ht_dcperiod*', 'talib-ht_dcphase*', 'talib-ht_phasor*', 
    'talib-ht_sine*', 'talib-ht_trendline*', 'talib-ht_trendmode*',

    # LINEAR REGRESSION EXTRAS (Slope is okay, but intercept is purely price-location math)
    'talib-linearreg_intercept*', 'talib-linearreg_angle*',

    # RAW PRICE REPRODUCTIONS (These are just OHLC re-packaged)
    'talib-avgprice*', 'talib-medprice*', 'talib-typprice*', 'talib-wclprice*'
]

FORCED_INDICATORS = [
    "example-multi-tf-rsi_EUR-USD_14_14_14_14",
    "example-multi-tf-rsi_DOLLAR.IDX-USD_14_14_14_14",
    "example-multi-tf-rsi_XAU-USD_14_14_14_14"
]

NUM_GENES = 16
CHUNK_MULT = 4

CONFIG = {
    'BASE_URL': "http://localhost:8000/ohlcv/1.1",
    'SYMBOL': "EUR-USD",
    'TIMEFRAME': "4h",
    'TARGET_INDICATOR': "example-pivot-finder_40",
    'START_DATE': "2021-01-01",
    'END_DATE': "2025-12-31",
    'LIMIT': 100000,
    'LOG_FILE': "alpha_factory_detailed_results.csv",
    'POP_SIZE': 3800,
    'GPU_CHUNK': 64 * CHUNK_MULT,               
    'GENE_COUNT': NUM_GENES,
    'MAX_COLS_PER_IND': 1,
    'TOTAL_INPUTS': NUM_GENES,
    'EPOCHS': 20,                   
    'LEARNING_RATE': 0.001,         
    'WEIGHT_MUTATION_RATE': 0.1,
    'FORCED_INDICATORS': FORCED_INDICATORS,
    'BLACKLISTED_INDICATORS': BLACKLISTED_INDICATORS,
    'MODE': 'BOTTOM'
}

DEVICE = torch.device("cuda")

def run():
    # Initialize the Sink Thread
    # It consumes the log_queue defined in reactor.py
    sink_thread = threading.Thread(target=async_sink_worker, daemon=True)
    sink_thread.start()

    # Setup folders
    os.makedirs("checkpoints", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    if not os.path.exists(CONFIG['LOG_FILE']):
        with open(CONFIG['LOG_FILE'], "w") as f: 
            f.write("timestamp,gen,f1,prec,rec,sigs,genes\n")

    ingestor = IndicatorIngestor(CONFIG)
    feats, targets, flat_universe = ingestor.get_data() 

    reactor = PersistentReactor(feats, targets, CONFIG, DEVICE)
    
    best_ever = 0.0
    print("\n" + "="*85)
    print(f"{'GEN':<6} | {'F1':<8} | {'PREC':<8} | {'REC':<8} | {'SIGS':<6} | {'FPS':<6}")
    print("-" * 85)

    try:
        for gen in range(100000):
            t0 = time.time()
            
            res = reactor.run_generation()
            
            if len(res['f1']) == 0:
                print(f"⚠️ GEN {gen} produced no results.")
                continue

            best_val, best_idx = torch.max(res['f1'], 0)
            max_sigs = int(res['sigs'].max().item())
            avg_f1 = res['f1'].mean().item()
            fps = CONFIG['POP_SIZE'] / (time.time() - t0)
            
            if best_val > best_ever:
                best_ever = best_val.item()
                cur_p = res['prec'][best_idx].item()
                cur_r = res['rec'][best_idx].item()
                cur_s = int(res['sigs'][best_idx].item())
                gn = [reactor.unique_inds[g] for g in reactor.population[best_idx]]
                
                print(f"\n🌟 {gen:<4} | {best_ever:.4f} | {cur_p:.4f} | {cur_r:.4f} | {cur_s:<6} | {fps:.1f}")
                print(f"   └─ Genes: {gn}")
                
                # --- ATOMIC SCAN TRIGGER ---
                if best_ever > 0.5:
                    print(f"   🔬 Triggering Atomic 6-Gene Scan for Ground Truth...")
                    reactor.run_atomic_scan(top_n_vitality=30, scan_size=8)
                
                log_entry = f"{datetime.now()},{gen},{best_ever:.4f},{cur_p:.4f},{cur_r:.4f},{cur_s},{'|'.join(gn)}"
                log_queue.put(("evolution.log", log_entry, False))

                checkpoint = {
                    'gen': gen, 'f1': best_ever, 'genes': gn,
                    'state_dict': {
                        'W1': reactor.pop_W1[best_idx].cpu(),
                        'W2': reactor.pop_W2[best_idx].cpu(),
                        'B1': reactor.pop_B1[best_idx].cpu(),
                        'B2': reactor.pop_B2[best_idx].cpu(),
                        'threshold': reactor.thresholds[best_idx].cpu()
                    }
                }
                log_queue.put((f"best_model_gen_{gen}.pt", checkpoint, True))

            else:
                print(f"🚜 {gen:<4} | Best: {best_val.item():.4f} | Avg: {avg_f1:.4f} | MaxSig: {max_sigs:<4} | FPS: {fps:.1f}")

            reactor.evolve(res['f1'].to(DEVICE))
            
            # Brief pause
            #time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[!] Shutdown Signal Received. Cleaning up...")
        log_queue.put(None)
        sink_thread.join(timeout=5) 
        print("Reactor Off. Fly safe.")

if __name__ == "__main__":
    run()