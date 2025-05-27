from utils import StatusParser

INPUT_FILENAME = "raw_statuses_dump_trump_2025.txt"

def process_statuses():
    try:
        with open(INPUT_FILENAME, 'r', encoding='utf-8') as f:
            for line_number, line_content_str in enumerate(f, 1):
                line_content_str = line_content_str.strip()
                if not line_content_str:
                    continue

                print(f"\n--- Processing line {line_number} ---")
                status_obj = StatusParser(line_content_str)

                if status_obj.is_valid():
                    print(f"  ID: {status_obj.id}")
                    print(f"  Content (cleaned): {status_obj.get_content(clean_html=True)}")
                    print(f"  Account: {status_obj.account_username}")
                else:
                    print(f"  Failed to parse line {line_number}. Error: {status_obj.parse_error}")

    except FileNotFoundError:
        print(f"Error: Input file '{INPUT_FILENAME}' not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    process_statuses()