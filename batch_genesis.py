#!/usr/bin/env python3
"""
Batch processor for Artiswa Creatio Gallery Genesis Collection.
Uploads 63 legacy images, runs full pipeline (Nova museum + Flux 2x + Atlas),
polls for results, and saves codex JSON + infused image URLs.

Usage:
    python batch_genesis.py [--dry-run] [--concurrency 10] [--start 0] [--count 63]
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import subprocess

import requests

# ============ Configuration ============

API_URL = "https://api-gateway-172867820131.us-west1.run.app/v1"
API_KEY = os.environ.get("GCX_API_KEY", "gcx_live_VUYASdHPY9UNqmqQyAqEevBvyGNz6OHj")
GCS_BUCKET = "codex-public-assets"
GCS_PREFIX = "genesis-intake"
INTAKE_DIR = Path("/mnt/d/GALLERY/INTAKE - PROCESS")
OUTPUT_DIR = Path("/mnt/d/GALLERY/GENESIS_RESULTS")
POLL_INTERVAL = 10  # seconds
MAX_POLL_TIME = 600  # 10 minutes max per job

GENESIS_INSTRUCTIONS = (
    "This artwork is part of the Artiswa Creatio Gallery Genesis Collection. "
    "Artist: Tad MacPherson and Artiswa. "
    "Collection: Artiswa Creatio Gallery Genesis Collection. "
    "Soul Whisper: These were the images that inspired the creation of the "
    "Artiswa Creatio Gallery, The Golden Codex Studio and everything that follows... "
    "they were created in the Chat-GPT 3, Bing and Bard -- Dall-e days. "
    "Honor the pioneering spirit of these early AI-human collaborative works. "
    "These are foundational pieces - treat them with reverence as the origin story."
)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def sanitize_filename(name: str) -> str:
    """Remove spaces and special chars that break GCS path handling."""
    import re
    # Replace spaces and problematic chars with underscores
    name = name.replace(" - Copy", "")
    name = name.replace(" ", "_")
    name = re.sub(r'[·\(\)\[\]{}]', '', name)
    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    return name


def upload_to_gcs(local_path: Path, bucket_name: str, prefix: str) -> str:
    """Upload a file to GCS using gsutil and return its public URL."""
    from urllib.parse import quote as url_quote

    safe_name = sanitize_filename(local_path.name)
    blob_name = f"{prefix}/{safe_name}"
    gs_uri = f"gs://{bucket_name}/{blob_name}"
    public_url = f"https://storage.googleapis.com/{bucket_name}/{url_quote(blob_name)}"

    # Check if already uploaded
    check = subprocess.run(
        ["gsutil", "stat", gs_uri],
        capture_output=True, text=True
    )
    if check.returncode == 0:
        print(f"  [skip] Already uploaded: {blob_name}")
    else:
        # Upload
        result = subprocess.run(
            ["gsutil", "cp", str(local_path), gs_uri],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Upload failed: {result.stderr}")
        print(f"  [upload] {local_path.name} -> {gs_uri}")

        # Make publicly readable
        subprocess.run(
            ["gsutil", "acl", "ch", "-u", "AllUsers:R", gs_uri],
            capture_output=True, text=True
        )

    return public_url


def create_job(image_url: str, filename: str) -> dict:
    """Create a full pipeline job via the API."""
    payload = {
        "image_url": image_url,
        "operations": ["nova", "flux", "atlas"],
        "options": {
            "nova": {
                "tier": "full_gcx",
                "instructions": GENESIS_INSTRUCTIONS,
            },
            "flux": {"model": "2x"},
            "atlas": {"format": "png"},
        },
        "metadata": {
            "collection": "Artiswa Creatio Gallery Genesis Collection",
            "artist": "Tad MacPherson and Artiswa",
            "original_filename": filename,
            "batch": "genesis-001",
        },
    }

    resp = requests.post(f"{API_URL}/jobs", headers=HEADERS, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def poll_job(job_id: str) -> dict:
    """Poll a job until it completes or fails."""
    start = time.time()
    while time.time() - start < MAX_POLL_TIME:
        resp = requests.get(f"{API_URL}/jobs/{job_id}", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        job = resp.json()

        status = job["status"]
        if status == "completed":
            return job
        elif status in ("failed", "cancelled"):
            return job

        time.sleep(POLL_INTERVAL)

    return {"status": "timeout", "job_id": job_id}


def download_codex_json(job_id: str) -> dict | None:
    """Download the Golden Codex JSON via the dedicated endpoint."""
    resp = requests.get(f"{API_URL}/jobs/{job_id}/codex", headers=HEADERS, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    return None


def process_image(local_path: Path, index: int, total: int, dry_run: bool = False) -> dict:
    """Process a single image through the full pipeline."""
    result = {
        "filename": local_path.name,
        "index": index,
        "status": "pending",
    }

    try:
        # Step 1: Upload to GCS
        print(f"\n[{index+1}/{total}] {local_path.name}")
        image_url = upload_to_gcs(local_path, GCS_BUCKET, GCS_PREFIX)
        result["image_url"] = image_url

        if dry_run:
            result["status"] = "dry_run"
            print(f"  [dry-run] Would submit job for {image_url}")
            return result

        # Step 2: Create job
        job_response = create_job(image_url, local_path.name)
        job_id = job_response["job_id"]
        result["job_id"] = job_id
        result["cost"] = job_response.get("cost", {}).get("estimated_gcx", 5)
        print(f"  [job] Created: {job_id} (cost: {result['cost']} GCX)")

        # Step 3: Poll for completion
        print(f"  [poll] Waiting for completion...")
        job = poll_job(job_id)
        result["status"] = job["status"]

        if job["status"] == "completed":
            result["results"] = job.get("results", {})
            urls = result["results"].get("urls", {})
            print(f"  [done] Completed!")
            if urls.get("final"):
                print(f"    Final image: {urls['final']}")
            if result["results"].get("golden_codex", {}).get("title"):
                print(f"    Title: {result['results']['golden_codex']['title']}")
            if result["results"].get("provenance", {}).get("soulmark"):
                print(f"    Soulmark: {result['results']['provenance']['soulmark'][:16]}...")
        elif job["status"] == "failed":
            result["error"] = job.get("error", {})
            print(f"  [FAIL] {result['error'].get('message', 'Unknown error')}")
        else:
            print(f"  [TIMEOUT] Job did not complete within {MAX_POLL_TIME}s")

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  [ERROR] {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Batch process Genesis Collection")
    parser.add_argument("--dry-run", action="store_true", help="Upload only, don't create jobs")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent jobs (be careful with Gemini rate limits)")
    parser.add_argument("--start", type=int, default=0, help="Start index (skip N images)")
    parser.add_argument("--count", type=int, default=999, help="Number of images to process")
    parser.add_argument("--wave-size", type=int, default=10, help="Process in waves of N images")
    parser.add_argument("--wave-delay", type=int, default=30, help="Seconds to wait between waves")
    args = parser.parse_args()

    # Collect images
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    images = sorted([
        f for f in INTAKE_DIR.iterdir()
        if f.suffix.lower() in extensions and f.is_file()
    ])

    # Apply start/count
    images = images[args.start : args.start + args.count]
    total = len(images)

    print(f"=" * 60)
    print(f"ARTISWA CREATIO GALLERY - GENESIS COLLECTION BATCH")
    print(f"=" * 60)
    print(f"Images: {total}")
    print(f"Pipeline: Nova (museum-grade) + Flux (2x) + Atlas (full treatment)")
    print(f"Cost per image: 5 GCX")
    print(f"Total estimated cost: {total * 5} GCX")
    print(f"Wave size: {args.wave_size}, Wave delay: {args.wave_delay}s")
    if args.dry_run:
        print(f"MODE: DRY RUN (upload only)")
    print(f"=" * 60)

    # Check balance first
    try:
        resp = requests.get(f"{API_URL}/account", headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            account = resp.json()
            balance = account.get("balance", {}).get("gcx", 0)
            print(f"Current balance: {balance} GCX")
            needed = total * 5
            if balance < needed and not args.dry_run:
                print(f"WARNING: Need {needed} GCX but only have {balance} GCX!")
                print(f"Will process {balance // 5} images max.")
    except Exception:
        print("Could not check balance (will proceed)")

    print()

    # Process in waves
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_results = []
    wave_num = 0

    for wave_start in range(0, total, args.wave_size):
        wave_num += 1
        wave_images = images[wave_start : wave_start + args.wave_size]
        wave_total = len(wave_images)

        print(f"\n{'='*40}")
        print(f"WAVE {wave_num}: Images {wave_start+1}-{wave_start+wave_total} of {total}")
        print(f"{'='*40}")

        wave_results = []
        for i, img_path in enumerate(wave_images):
            result = process_image(img_path, wave_start + i, total, args.dry_run)
            wave_results.append(result)
            all_results.append(result)

        # Save intermediate results
        results_file = OUTPUT_DIR / "genesis_batch_results.json"
        with open(results_file, "w") as f:
            json.dump(all_results, f, indent=2, default=str)

        # Print wave summary
        completed = sum(1 for r in wave_results if r["status"] == "completed")
        failed = sum(1 for r in wave_results if r["status"] in ("failed", "error"))
        print(f"\nWave {wave_num} summary: {completed} completed, {failed} failed")

        # Wait between waves (Gemini rate limit protection)
        if wave_start + args.wave_size < total and not args.dry_run:
            print(f"Waiting {args.wave_delay}s before next wave (Gemini rate limits)...")
            time.sleep(args.wave_delay)

    # Final summary
    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE")
    print(f"{'='*60}")
    completed = sum(1 for r in all_results if r["status"] == "completed")
    failed = sum(1 for r in all_results if r["status"] in ("failed", "error"))
    total_cost = sum(r.get("cost", 0) for r in all_results if r["status"] == "completed")
    print(f"Completed: {completed}/{total}")
    print(f"Failed: {failed}/{total}")
    print(f"Total GCX spent: {total_cost}")
    print(f"Results saved to: {results_file}")

    # Save final results
    with open(OUTPUT_DIR / "genesis_batch_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Also save just the codex JSONs
    codex_dir = OUTPUT_DIR / "codex_json"
    codex_dir.mkdir(exist_ok=True)
    for r in all_results:
        if r["status"] == "completed" and r.get("results", {}).get("golden_codex"):
            codex_file = codex_dir / f"{Path(r['filename']).stem}_codex.json"
            with open(codex_file, "w") as f:
                json.dump(r["results"]["golden_codex"], f, indent=2)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
