#!/bin/bash
npx concurrently \
  "npm run dev" \
  "cd backend && sh test_dev.sh"