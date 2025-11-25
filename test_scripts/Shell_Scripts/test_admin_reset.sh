#!/bin/bash

# Quick test for admin reset endpoint (without actually resetting)
# This tests authentication only

API_URL="https://ngrssolver08.comcentricapps.com"

echo "================================================================================"
echo "ADMIN RESET ENDPOINT TEST"
echo "================================================================================"
echo ""

# Test 1: Missing API key
echo "Test 1: Missing API key (should fail with 422)"
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "${API_URL}/admin/reset")
HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')
echo "Status: $HTTP_STATUS"
if [ "$HTTP_STATUS" = "422" ]; then
    echo "✅ PASS: Missing API key rejected"
else
    echo "❌ FAIL: Expected 422, got $HTTP_STATUS"
fi
echo ""

# Test 2: Invalid API key
echo "Test 2: Invalid API key (should fail with 401)"
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "${API_URL}/admin/reset" -H "x-api-key: invalid-key")
HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')
echo "Status: $HTTP_STATUS"
if [ "$HTTP_STATUS" = "401" ]; then
    echo "✅ PASS: Invalid API key rejected"
else
    echo "❌ FAIL: Expected 401, got $HTTP_STATUS"
fi
echo ""

# Test 3: Valid API key (requires ADMIN_API_KEY env var)
if [ -n "$ADMIN_API_KEY" ] && [ "$ADMIN_API_KEY" != "change-me-in-production" ]; then
    echo "Test 3: Valid API key (will attempt reset)"
    echo "⚠️  Skipping actual reset - use ./admin_reset.sh for real reset"
else
    echo "Test 3: Valid API key test skipped"
    echo "ℹ️  Set ADMIN_API_KEY environment variable to test with valid key"
fi

echo ""
echo "================================================================================"
echo "CURRENT PRODUCTION API KEY STATUS"
echo "================================================================================"

# Try to determine if API key is set on server
RESPONSE=$(curl -s -X POST "${API_URL}/admin/reset" -H "x-api-key: test-probe")
if echo "$RESPONSE" | grep -q "Invalid API key"; then
    echo "✅ Production server has ADMIN_API_KEY configured"
    echo "   (Default 'change-me-in-production' or custom key)"
else
    echo "⚠️  Production server API key status unclear"
fi

echo ""
echo "================================================================================"
echo "SETUP INSTRUCTIONS"
echo "================================================================================"
echo ""
echo "To use the admin reset endpoint in production:"
echo ""
echo "1. Set ADMIN_API_KEY on the server:"
echo "   AWS App Runner: Configuration → Environment Variables"
echo "   Add: ADMIN_API_KEY = <your-secure-key>"
echo ""
echo "2. Deploy the configuration change"
echo ""
echo "3. Set the same key locally:"
echo "   export ADMIN_API_KEY='<your-secure-key>'"
echo ""
echo "4. Run reset:"
echo "   ./admin_reset.sh"
echo ""
echo "================================================================================"
