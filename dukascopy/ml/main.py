import os, time, torch
from datetime import datetime
from ingest import IndicatorIngestor
from reactor import PersistentReactor

CONFIG = {
    'BASE_URL': "http://localhost:8000/ohlcv/1.1",
    'SYMBOL': "EUR-USD",
    'TIMEFRAME': "1h",
    'TARGET_INDICATOR': "example-pivot-finder",
    'START_DATE': "2018-01-01",
    'END_DATE': "2023-01-01",
    'LOG_FILE': "alpha_factory_detailed_results.csv",
    'POP_SIZE': 4096,
    'GPU_CHUNK': 512,
    'GENE_COUNT': 6,
    'MAX_COLS_PER_IND': 5,
    'TOTAL_INPUTS': 6 * 5,
    'EPOCHS': 100,
    'LEARNING_RATE': 0.005,
    'WEIGHT_MUTATION_RATE': 0.01,
    'FORCED_INDICATORS': [
        "example-multi-tf-rsi_DOLLAR.IDX-USD_14_14_14_14",
        "example-multi-tf-rsi_EUR-USD_14_14_14_14",
        "example-multi-tf-rsi_XAU-USD_14_14_14_14"
    ],
    'BLACKLISTED_INDICATORS': [
        "*example-pivot-finder*",
        "zigzag*",
        "example-elliot*",
        "pivot*",
        "camarilla*",
        "psychlevels*",
        "talib-*",
        "open",
        "high",
        "low",
        "close",
        "volume",

        "example-macro*",
        "fibonacci*"
    ]

}

DEVICE = torch.device("cuda")

def run():
    if not os.path.exists(CONFIG['LOG_FILE']):
        with open(CONFIG['LOG_FILE'], "w") as f: 
            f.write("timestamp,gen,f1,prec,rec,sigs,genes\n")

    # Ingest
    ingestor = IndicatorIngestor(CONFIG)
    feats, targets = ingestor.get_data()

    # Setup Reactor
    reactor = PersistentReactor(feats, targets, CONFIG, DEVICE)
    
    best_ever = 0.0
    print("\n" + "="*85)
    print(f"{'GEN':<6} | {'F1':<8} | {'PREC':<8} | {'REC':<8} | {'SIGS':<6} | {'FPS':<6}")
    print("-" * 85)

    # Training Loop
    for gen in range(100000):
        t0 = time.time()

        t0 = time.time()
        
        # Only profile once every 100 generations to keep the CPU out of the way
        do_profile = (gen % 5 == 0)
        do_profile = False
        res = reactor.run_generation(do_profile=do_profile)
        
        best_val, best_idx = torch.max(res['f1'], 0)
        fps = CONFIG['POP_SIZE'] / (time.time() - t0)
        
        if best_val > best_ever:
            best_ever = best_val.item()
            cur_p = res['prec'][best_idx].item()
            cur_r = res['rec'][best_idx].item()
            cur_s = int(res['sigs'][best_idx].item())
            gn = [reactor.unique_inds[g] for g in reactor.population[best_idx]]
            
            print(f"🌟 {gen:<4} | {best_ever:.4f} | {cur_p:.4f} | {cur_r:.4f} | {cur_s:<6} | {fps:.1f}")
            print(f"   └─ Genes: {gn}")
            
            with open(CONFIG['LOG_FILE'], "a") as f:
                f.write(f"{datetime.now()},{gen},{best_ever:.4f},{cur_p:.4f},{cur_r:.4f},{cur_s},{'|'.join(gn)}\n")
        
        elif gen % 5 == 0:
            print(f"💨 {gen:<4} | {best_ever:.4f} (Avg:{res['f1'].mean():.4f}) | FPS: {fps:.1f}", end="\r")
        
        reactor.evolve(res['f1'])

if __name__ == "__main__":
    run()