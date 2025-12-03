#!/usr/bin/env python3
"""
Ratio Cache Management CLI Tool

Manage the optimal ratio cache for production deployment.

Usage:
    python src/manage_ratio_cache.py stats          # Show cache statistics
    python src/manage_ratio_cache.py list           # List all cached ratios
    python src/manage_ratio_cache.py clear          # Clear entire cache
    python src/manage_ratio_cache.py invalidate <hash>  # Remove specific pattern
    python src/manage_ratio_cache.py export         # Export cache to JSON

Examples:
    # View cache stats
    python src/manage_ratio_cache.py stats
    
    # Clear cache before testing
    python src/manage_ratio_cache.py clear
    
    # Export cache for backup
    python src/manage_ratio_cache.py export > backup_cache.json
"""

import sys
import argparse
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.ratio_cache import RatioCache


def cmd_stats(cache: RatioCache):
    """Display cache statistics."""
    cache.print_stats()


def cmd_list(cache: RatioCache):
    """List all cached patterns in detail."""
    stats = cache.get_stats()
    
    if not stats.get('patterns'):
        print("📭 Cache is empty")
        return
    
    print(f"\n{'='*80}")
    print("CACHED OPTIMAL RATIOS")
    print(f"{'='*80}\n")
    
    for i, pattern in enumerate(stats['patterns'], 1):
        print(f"{i}. Pattern: {pattern['pattern']} (hash: {pattern['hash']})")
        print(f"   Optimal Ratio: {pattern['ratio']:.0%} strict / {(1-pattern['ratio']):.0%} flexible")
        print(f"   Employees Used: {pattern['employees']}")
        print(f"   Usage Count: {pattern['usageCount']}")
        print(f"   Last Used: {pattern['lastUsed']}")
        print()
    
    print(f"Total: {len(stats['patterns'])} cached pattern(s)")
    print(f"{'='*80}\n")


def cmd_clear(cache: RatioCache, force: bool = False):
    """Clear entire cache."""
    stats = cache.get_stats()
    entry_count = stats['totalEntries']
    
    if entry_count == 0:
        print("📭 Cache is already empty")
        return
    
    if not force:
        print(f"⚠️  This will delete {entry_count} cached ratio(s)")
        response = input("Are you sure? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ Cancelled")
            return
    
    cache.clear_cache()
    print(f"✅ Cleared {entry_count} cached ratio(s)")


def cmd_invalidate(cache: RatioCache, pattern_hash: str):
    """Invalidate specific pattern by hash."""
    stats = cache.get_stats()
    
    # Find the pattern
    pattern_entry = None
    for p in stats.get('patterns', []):
        if p['hash'] == pattern_hash or p['hash'].startswith(pattern_hash):
            pattern_entry = p
            break
    
    if not pattern_entry:
        print(f"❌ Pattern hash '{pattern_hash}' not found in cache")
        print("\nAvailable hashes:")
        for p in stats.get('patterns', []):
            print(f"  • {p['hash']}: {p['pattern']}")
        return
    
    # Remove from cache
    if "entries" in cache.cache and pattern_entry['hash'] in cache.cache["entries"]:
        del cache.cache["entries"][pattern_entry['hash']]
        cache._save_cache()
        print(f"✅ Invalidated pattern: {pattern_entry['pattern']} (hash: {pattern_entry['hash']})")
    else:
        print(f"❌ Could not invalidate pattern")


def cmd_export(cache: RatioCache):
    """Export cache as JSON to stdout."""
    print(json.dumps(cache.cache, indent=2, default=str))


def cmd_import(cache: RatioCache, json_file: str):
    """Import cache from JSON file."""
    try:
        with open(json_file, 'r') as f:
            imported_cache = json.load(f)
        
        # Validate structure
        if "version" not in imported_cache or "entries" not in imported_cache:
            print("❌ Invalid cache format")
            return
        
        # Merge with existing cache
        existing_entries = cache.cache.get("entries", {})
        imported_entries = imported_cache.get("entries", {})
        
        new_count = 0
        updated_count = 0
        
        for hash_key, entry in imported_entries.items():
            if hash_key in existing_entries:
                updated_count += 1
            else:
                new_count += 1
            existing_entries[hash_key] = entry
        
        cache.cache["entries"] = existing_entries
        cache._save_cache()
        
        print(f"✅ Import complete:")
        print(f"   New patterns: {new_count}")
        print(f"   Updated patterns: {updated_count}")
    
    except FileNotFoundError:
        print(f"❌ File not found: {json_file}")
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in file: {json_file}")
    except Exception as e:
        print(f"❌ Import failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage the optimal ratio cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/manage_ratio_cache.py stats
  python src/manage_ratio_cache.py list
  python src/manage_ratio_cache.py clear --force
  python src/manage_ratio_cache.py invalidate abc123
  python src/manage_ratio_cache.py export > backup.json
  python src/manage_ratio_cache.py import backup.json
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # stats command
    subparsers.add_parser('stats', help='Show cache statistics')
    
    # list command
    subparsers.add_parser('list', help='List all cached patterns')
    
    # clear command
    clear_parser = subparsers.add_parser('clear', help='Clear entire cache')
    clear_parser.add_argument('--force', action='store_true', help='Skip confirmation')
    
    # invalidate command
    invalidate_parser = subparsers.add_parser('invalidate', help='Remove specific pattern')
    invalidate_parser.add_argument('hash', help='Pattern hash to invalidate')
    
    # export command
    subparsers.add_parser('export', help='Export cache to JSON (stdout)')
    
    # import command
    import_parser = subparsers.add_parser('import', help='Import cache from JSON')
    import_parser.add_argument('file', help='JSON file to import')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize cache
    cache = RatioCache()
    
    # Execute command
    if args.command == 'stats':
        cmd_stats(cache)
    elif args.command == 'list':
        cmd_list(cache)
    elif args.command == 'clear':
        cmd_clear(cache, force=args.force)
    elif args.command == 'invalidate':
        cmd_invalidate(cache, args.hash)
    elif args.command == 'export':
        cmd_export(cache)
    elif args.command == 'import':
        cmd_import(cache, args.file)


if __name__ == '__main__':
    main()
