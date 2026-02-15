import argparse
import sys
import importlib
from pathlib import Path
from generators.sidetracking.base import ConfigGenerator

class CustomArgumentParser(argparse.ArgumentParser):
    """
    Custom ArgumentParser that prints a specific example on error.
    """
    def error(self, message):
        sys.stderr.write(f"Error: {message}\n\n")
        sys.stderr.write("Example Run:\n")
        sys.stderr.write(f"./build-sidetracking-config.sh \\\n")
        sys.stderr.write("  --symbol BRENT.CMD-USD-PANAMA \\\n")
        sys.stderr.write("  --source BRENT.CMD-USD \\\n")
        sys.stderr.write("  --class generators.sidetracking.extensions.dukascopy.DukascopyPanamaStrategy \\\n")
        sys.stderr.write("  --output config.user/dukascopy/sidetracking/BRENT.CMD-USD-PANAMA.yaml\n")
        sys.exit(2)

def load_class(class_path: str):
    """
    Directly handles the 'config.user' folder anchor.
    Converts trailing dots to slashes to locate the .py file.
    """
    parts = class_path.split('.')
    class_name = parts.pop()
    
    # Check for our specific folder anchor
    if "config.user" in class_path:        
        path_str = class_path.replace(class_name, "").rstrip('.')
        # Replace only the dots occurring AFTER config.user
        if path_str.startswith("config.user."):
            sub_path = path_str.replace("config.user.", "").replace(".", "/")
            file_path = Path(f"config.user/{sub_path}.py")
        else:
            # It's just config.user.FileName
            file_path = Path(path_str.replace(".", "/") + ".py")
            
        if file_path.is_file():
            module_name = "custom_module" # Internal alias
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path.resolve())
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return getattr(module, class_name)
            except Exception as e:
                print(f"Error loading {class_name} from {file_path}: {e}")
                sys.exit(1)

    # Standard Fallback for core generators or site-packages
    try:
        module_path = ".".join(parts)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except Exception as e:
        print(f"Error: Could not resolve '{class_path}'.\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = CustomArgumentParser(
        description="Generate Corporate Action Configs (Panama, Splits, etc.)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("--symbol", required=True, help="Target Symbol Name")
    parser.add_argument("--source", required=True, help="Source Data Name")
    parser.add_argument("--class", dest="strategy_class", required=True, 
                        help="Full python path to strategy class")
    
    parser.add_argument("--output", help="Path to save the YAML file. If omitted, prints to stdout.")

    args = parser.parse_args()

    StrategyClass = load_class(args.strategy_class)
    
    try:
        strategy = StrategyClass()
        generator = ConfigGenerator(strategy)
    except Exception as e:
        print(f"Error: Failed to instantiate {args.strategy_class}.\n{e}")
        sys.exit(1)

    print(f"--- Generating Config for {args.symbol} using {StrategyClass.__name__} ---")

    try:
        yaml_output = generator.build_yaml(args.symbol, args.source)
    except Exception as e:
        print(f"Error during generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            f.write(yaml_output)
        print(f"Success: Configuration written to {output_path}")
    else:
        print("\n" + "="*40)
        print("       GENERATED CONFIGURATION       ")
        print("="*40 + "\n")
        print(yaml_output)