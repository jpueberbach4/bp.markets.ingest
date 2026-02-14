from generators.sidetracking.base import ConfigGenerator
from generators.sidetracking.extensions.dukascopy import DukascopyPanamaStrategy

if __name__ == "__main__":
    TARGET_SYMBOL = "BRENT.CMD-USD-PANAMA"
    SOURCE_NAME = "BRENT.CMD-USD"
    
    # Instantiate Strategy
    strategy = DukascopyPanamaStrategy()
    
    # Instantiate Generator
    generator = ConfigGenerator(strategy)
    
    print(f"--- Generating Config for {TARGET_SYMBOL} ---")
    
    # Run
    yaml_output = generator.build_yaml(TARGET_SYMBOL, SOURCE_NAME)
    
    # Output
    print("\n" + "="*40)
    print("       GENERATED CONFIGURATION       ")
    print("="*40 + "\n")
    print(yaml_output)
    
    # Optional: Save to file
    # with open(f"{TARGET_SYMBOL}_config.yaml", "w") as f:
    #     f.write(yaml_output)