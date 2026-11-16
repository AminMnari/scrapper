#!/usr/bin/env python
"""
Quick test to verify Cloudflare bypass setup is working correctly.
Run this before attempting to scrape tanitjobs.com
"""

import logging
import sys
import importlib.util

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_setup():
    """Test if all Cloudflare bypass components are installed and configured."""
    
    logger.info("╔════════════════════════════════════════════════════════════╗")
    logger.info("║   Cloudflare Bypass Setup Verification                    ║")
    logger.info("╚════════════════════════════════════════════════════════════╝")
    
    # Test 1: Config imports
    logger.info("\n[1/4] Testing config imports...")
    try:
        from config import (
            BROWSER_USE_UNDETECTED, BROWSER_HEADLESS,
            BROWSER_USE_PROFILE, BROWSER_USER_DATA_DIR, CHALLENGE_WAIT_SECONDS
        )
        logger.info("✓ Config imported successfully")
    except ImportError as e:
        logger.error(f"✗ Failed to import config: {e}")
        return False
    
    # Test 2: Undetected chromedriver is installed
    logger.info("\n[2/4] Checking undetected-chromedriver installation...")
    try:
        if importlib.util.find_spec("undetected_chromedriver") is None:
            raise ImportError("undetected_chromedriver not found")
        logger.info("✓ undetected-chromedriver is installed")
    except ImportError:
        logger.warning("✗ undetected-chromedriver NOT installed")
        logger.info("   To install: pip install undetected-chromedriver")
        return False
    
    # Test 3: Selenium is installed
    logger.info("\n[3/4] Checking Selenium installation...")
    try:
        from selenium import webdriver
        logger.info("✓ Selenium is installed")
    except ImportError:
        logger.error("✗ Selenium NOT installed")
        return False
    
    # Test 4: Display configuration
    logger.info("\n[4/4] Current Configuration:")
    logger.info(f"   • Undetected ChromeDriver Enabled: {BROWSER_USE_UNDETECTED}")
    logger.info(f"   • Headless Mode: {BROWSER_HEADLESS}")
    logger.info(f"   • Browser Profile Enabled: {BROWSER_USE_PROFILE}")
    logger.info(f"   • Profile Directory: {BROWSER_USER_DATA_DIR}")
    logger.info(f"   • Cloudflare Timeout: {CHALLENGE_WAIT_SECONDS}s")
    
    logger.info("\n╔════════════════════════════════════════════════════════════╗")
    logger.info("║   ✓ Setup VERIFIED - Ready to scrape!                    ║")
    logger.info("╚════════════════════════════════════════════════════════════╝")
    
    logger.info("\nNEXT STEPS:")
    logger.info("1. Make sure you have undetected-chromedriver installed:")
    logger.info("   pip install undetected-chromedriver")
    logger.info("\n2. Test with tanitjobs.com scraping:")
    logger.info("   python main.py  # or your scraping command")
    logger.info("\n3. A browser window will open - keep it in focus!")
    logger.info("   If Cloudflare appears, it will auto-bypass or wait for you.")
    
    return True

if __name__ == "__main__":
    success = test_setup()
    sys.exit(0 if success else 1)
