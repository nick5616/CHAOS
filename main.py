import argparse
import yaml
import os
from chaos_lib import ingestion, analyzers, correlator, clipper, summary

def main():
    parser = argparse.ArgumentParser(description="CHAOS: CS2 Highlight Analysis & Organization System")
    parser.add_argument('stage', choices=['all', 'ingest', 'analyze', 'correlate', 'clip', 'summary'], 
                        help="The pipeline stage to run.")
    args = parser.parse_args()

    print("Loading configuration from config.yaml...")
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

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