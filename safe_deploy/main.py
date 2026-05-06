import os
import sys

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    secret = os.getenv("APP_SECRET")

    if not secret:
        print("Error: APP_SECRET not found in environment!")
        sys.exit(1)

    print(f"System started. Secret hash: {secret[:3]}***")


if __name__ == "__main__":
    main()
