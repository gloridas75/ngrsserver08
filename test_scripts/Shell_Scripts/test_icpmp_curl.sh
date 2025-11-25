#!/bin/bash

echo "Testing ICPMP Production Endpoint"
echo "=================================="
echo ""
echo "Endpoint: https://ngrssolver08.comcentricapps.com/configure"
echo "Input: input/requirements_simple.json"
echo "Output: output/icpmp_production_test.json"
echo ""

curl -X POST \
  https://ngrssolver08.comcentricapps.com/configure \
  -H "Content-Type: application/json" \
  -d @input/requirements_simple.json \
  -o output/icpmp_production_test.json \
  -w "\nHTTP Status: %{http_code}\nTime: %{time_total}s\n" \
  --max-time 300

echo ""
echo "Response saved to: output/icpmp_production_test.json"
