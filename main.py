# === FILE: main.py ===
import argparse
import yaml
import os
from chaos_lib import ingestion, analyzers, correlator, clipper, summary

def main():
    parser = argparse.ArgumentParser(description="CHAOS: CS2 Highlight Analysis & Organization System")
    parser.add_argument('stage', choices=['all', 'ingest', 'analyze', 'correlate', 'clip', 'summary'], 
                        help="The pipeline stage to run.")
    parser.add_argument('--debug', action='store_true', 
                        help="Run in debug mode. Processes only the first video found in the manifest.")
    args = parser.parse_args()

    print("Loading configuration from config.yaml...")
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Add the debug flag to the config to make it accessible by other modules
    config['debug_mode'] = args.debug
    if config['debug_mode']:
        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!!  DEBUG MODE IS ENABLED           !!!")
        print("!!!  Only ONE video will be processed. !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")

    # Ensure output directories exist
    os.makedirs(config['data_folder'], exist_ok=True)
    os.makedirs(config['final_clips_folder'], exist_ok=True)

    if args.stage in ['all', 'ingest']:
        print("\n--- Running Stage: Ingestion ---")
        ingestion.create_manifest(config)

    if args.stage in ['all', 'analyze']:
        print("\n--- Running Stage: Analysis ---")
        analyzers.run_analysis(config)

    if args.stage in ['all', 'correlate']:
        print("\n--- Running Stage: Correlation ---")
        correlator.run_correlation(config)

    if args.stage in ['all', 'summary']:
        print("\n--- Running Stage: Summary Generation ---")
        summary.generate_summary(config)

    if args.stage in ['all', 'clip']:
        print("\n--- Running Stage: Clipping ---")
        clipper.run_clipping(config)

if __name__ == "__main__":
    main()