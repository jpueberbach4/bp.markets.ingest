import os, time, torch
from datetime import datetime
from ingest import IndicatorIngestor
from reactor import PersistentReactor

# Cleaned up Blacklist
BLACKLISTED_INDICATORS = [
    'zigzag*', 'swing-points*', 'fractaldimension*', 'kalman*', 
    'open', 'high', 'low', 'close', 'volume', 
    'is-open*', 'pivot*', 'camarilla-pivots*', 'psychlevels*', 
    'sma*', 'midpoint*', 'drift*', 
    "*example-pivot-finder*", 
    "*elliot*", 
    "feature*"
    # "talib*"  <-- Keep TA-Lib unless you have a custom 122-feature set.
]

FORCED_INDICATORS = [
    "example-multi-tf-rsi_EUR-USD_14_14_14_14",
    "example-multi-tf-rsi_DOLLAR.IDX-USD_14_14_14_14",
    "example-multi-tf-rsi_XAU-USD_14_14_14_14"
]

NUM_GENES = 12
CHUNK_MULT = 4

CONFIG = {
    'BASE_URL': "http://localhost:8000/ohlcv/1.1",
    'SYMBOL': "EUR-USD",
    'TIMEFRAME': "4h",
    'TARGET_INDICATOR': "example-pivot-finder",
    'START_DATE': "2019-01-01",
    'END_DATE': "2023-01-01",
    'LOG_FILE': "alpha_factory_detailed_results.csv",
    'POP_SIZE': 4096,
    'GPU_CHUNK': 64 * CHUNK_MULT,               
    'GENE_COUNT': NUM_GENES,
    'MAX_COLS_PER_IND': 1,
    'TOTAL_INPUTS': NUM_GENES,
    'EPOCHS': 20,                  
    'LEARNING_RATE': 0.001,        
    'WEIGHT_MUTATION_RATE': 0.1,
    'FORCED_INDICATORS': FORCED_INDICATORS,
    'BLACKLISTED_INDICATORS': BLACKLISTED_INDICATORS
}

DEVICE = torch.device("cuda")

def run():
    if not os.path.exists(CONFIG['LOG_FILE']):
        with open(CONFIG['LOG_FILE'], "w") as f: 
            f.write("timestamp,gen,f1,prec,rec,sigs,genes\n")

    ingestor = IndicatorIngestor(CONFIG)
    feats, targets, flat_universe = ingestor.get_data() 

    # Pass the features and targets to the reactor as before
    reactor = PersistentReactor(feats, targets, CONFIG, DEVICE)
    
    best_ever = 0.0
    print("\n" + "="*85)
    print(f"{'GEN':<6} | {'F1':<8} | {'PREC':<8} | {'REC':<8} | {'SIGS':<6} | {'FPS':<6}")
    print("-" * 85)

    for gen in range(100000):
        t0 = time.time()
        res = reactor.run_generation()
        
        # Stability: Ensure we actually have results before processing
        if len(res['f1']) == 0:
            print(f"⚠️ GEN {gen} produced no results. Check GPU/Heat.")
            continue

        best_val, best_idx = torch.max(res['f1'], 0)
        max_sigs = int(res['sigs'].max().item())
        avg_f1 = res['f1'].mean().item()
        fps = CONFIG['POP_SIZE'] / (time.time() - t0)
        
        if best_val > best_ever:
            best_ever = best_val.item()
            
            # Use .get() or check keys to prevent KeyError: 'prec'
            cur_p = res['prec'][best_idx].item() if 'prec' in res else 0.0
            cur_r = res['rec'][best_idx].item() if 'rec' in res else 0.0
            cur_s = int(res['sigs'][best_idx].item())
            
            gn = [reactor.unique_inds[g] for g in reactor.population[best_idx]]
            
            print(f"\n🌟 {gen:<4} | {best_ever:.4f} | {cur_p:.4f} | {cur_r:.4f} | {cur_s:<6} | {fps:.1f}")
            print(f"   └─ Genes: {gn}")
            
            with open(CONFIG['LOG_FILE'], "a") as f:
                f.write(f"{datetime.now()},{gen},{best_ever:.4f},{cur_p:.4f},{cur_r:.4f},{cur_s},{'|'.join(gn)}\n")

            checkpoint = {
                'gen': gen,
                'f1': best_ever,
                'genes': gn,
                'state_dict': {
                    'W1': reactor.pop_W1[best_idx].cpu(),
                    'W2': reactor.pop_W2[best_idx].cpu(),
                    'B1': reactor.pop_B1[best_idx].cpu(),
                    'B2': reactor.pop_B2[best_idx].cpu(),
                    'threshold': reactor.thresholds[best_idx].cpu()
                }
            }
            torch.save(checkpoint, f"best_model_gen_{gen}.pt")
            print(f"   💾 Checkpoint saved: best_model_gen_{gen}.pt")

        else:
            print(f"🚜 {gen:<4} | Best: {best_val.item():.4f} | Avg: {avg_f1:.4f} | MaxSig: {max_sigs:<4} | FPS: {fps:.1f}")

        reactor.evolve(res['f1'])
        
        # Laptop Survival Pause
        time.sleep(10.0)

if __name__ == "__main__":
    run()