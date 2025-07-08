#!/bin/bash

# A script to validate gcloud configuration and then run terraform init.

# Define some colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "--- GCloud & Terraform Initializer ---"
echo

# --- 1. Validate gcloud authentication ---
echo "Step 1: Checking gcloud authentication..."
ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null)
if [ -z "$ACTIVE_ACCOUNT" ]; then
    echo -e "${RED}Error: Not authenticated to gcloud.${NC}"
    echo "Please run 'gcloud auth login' and 'gcloud auth application-default login' first."
    exit 1
fi
echo -e "${GREEN}Authentication check passed.${NC}"
echo

# --- 2. Gather and validate configuration ---
echo "Step 2: Gathering gcloud configuration..."
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION=$(gcloud config get-value compute/region 2>/dev/null)

# Project ID is mandatory for Terraform
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No gcloud project is set.${NC}"
    echo "Please set your project using 'gcloud config set project <PROJECT_ID>'."
    exit 1
fi

# Region is optional but good to have.
if [ -z "$REGION" ]; then
    REGION_DISPLAY="${YELLOW}Not Set (but this might be okay)${NC}"
else
    REGION_DISPLAY="${YELLOW}${REGION}${NC}"
fi

# --- 3. Confirm all settings at once ---
echo "Please confirm your gcloud configuration:"
echo -e "  - Account:  ${YELLOW}${ACTIVE_ACCOUNT}${NC}"
echo -e "  - Project:  ${YELLOW}${PROJECT_ID}${NC}"
echo -e "  - Region:   ${REGION_DISPLAY}"
echo -e "  - Environment: ${YELLOW}production${NC}"
echo

read -p "Is this configuration correct? (y/n) " -n 1 -r
echo # move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Aborting.${NC} Please review your configuration."
    echo "You can set the correct values using:"
    echo "  gcloud config set account <ACCOUNT>"
    echo "  gcloud config set project <PROJECT_ID>"
    echo "  gcloud config set compute/region <REGION>"
    exit 1
fi

echo -e "\n${GREEN}Configuration confirmed.${NC}"

# --- 4. Run terraform init ---
echo "--- All checks passed. Proceeding with Terraform initialization. ---"
echo
terraform init

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}Terraform has been successfully initialized!${NC}"
else
    echo -e "\n${RED}Terraform initialization failed.${NC}"
    exit 1
fi

exit 0