from truthbrush import Api

TARGET_USERNAME = "realDonaldTrump"

# Set an ID as a string (e.g., "114499337476531986")
SINCE_ID_FILTER = '114520307594338802'

OUTPUT_FILENAME_RAW_STATUSES = "raw_statuses_dump_trump_2025.txt"
API_VERBOSE_OUTPUT = True


def main():
    api = Api()

    print(f"[*] Fetching statuses for user '{TARGET_USERNAME}'...")
    if SINCE_ID_FILTER:
        print(f"[*] Only statuses newer than ID: {SINCE_ID_FILTER}")
    if not API_VERBOSE_OUTPUT:
        print(f"[*] Verbose API output (to console) is disabled.")


    try:
        statuses = api.pull_statuses(
            username=TARGET_USERNAME,
            replies=False, # Hardcoded to False
            verbose=API_VERBOSE_OUTPUT, # Controls truthbrush's own console verbosity
            since_id=SINCE_ID_FILTER
        )
    except Exception as e:
        print(f"[!] Error fetching statuses: {e}")
        return

    if not statuses:
        print("[-] No statuses found.")
        return

    # --- Write raw statuses to file ---
    try:
        with open(OUTPUT_FILENAME_RAW_STATUSES, 'w', encoding='utf-8') as f_raw:
            for status in statuses:
                # str(status) converts the Python dictionary to its string representation
                f_raw.write(str(status) + "\n")
        print(f"[+] Raw status objects (string representation of each) successfully written to '{OUTPUT_FILENAME_RAW_STATUSES}'")
    except IOError as e:
        print(f"[!] Error writing raw statuses to file '{OUTPUT_FILENAME_RAW_STATUSES}': {e}")

if __name__ == "__main__":
    main()