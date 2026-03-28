#!/bin/bash
# mnemo install script
# Run from the mnemo directory: bash install.sh

set -e

PURPLE='\033[95m'
GREEN='\033[92m'
GRAY='\033[90m'
RESET='\033[0m'
BOLD='\033[1m'

echo ""
echo -e "${PURPLE}${BOLD}mnemo${RESET} — installing"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required. Install from https://python.org"
    exit 1
fi

echo -e "${GRAY}Python $(python3 --version | cut -d' ' -f2) found${RESET}"

# Install anthropic SDK
echo -e "${GRAY}installing anthropic SDK...${RESET}"
pip3 install anthropic --quiet --break-system-packages 2>/dev/null || pip3 install anthropic --quiet

# Make scripts executable
chmod +x mnemo.py reflect.py

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo ""
    echo -e "${PURPLE}Almost there.${RESET} Add your API key to your shell profile:"
    echo ""
    echo "  echo 'export ANTHROPIC_API_KEY=your_key_here' >> ~/.zshrc"
    echo "  source ~/.zshrc"
    echo ""
    echo "Get your key at: https://console.anthropic.com"
else
    echo -e "${GREEN}API key found${RESET}"
fi

echo ""
echo -e "${GREEN}${BOLD}done.${RESET}"
echo ""
echo "To start a conversation:"
echo -e "  ${PURPLE}python3 mnemo.py${RESET}"
echo ""
echo "To open the 3D memory visualiser:"
echo -e "  ${PURPLE}open visualise.html${RESET}  (then load graph.json)"
echo ""
echo "Or serve it locally for auto-loading:"
echo -e "  ${PURPLE}python3 -m http.server 8765${RESET}  then open http://localhost:8765/visualise.html"
echo ""
