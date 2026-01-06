from args import parse_args
from pathlib import Path
from config.app_config import load_app_config

def main():
    config_file = 'config.user.yaml' if Path("config.user.yaml").exists() else 'config.user.yaml'

    config = load_app_config(config_file)

    print(config)
    pass

if __name__ == "__main__":
    main()
