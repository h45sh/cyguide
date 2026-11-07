#!/usr/bin/env bash
# ==============================================================================
# CyGuide Universal Dependency & Tool Installer
# ==============================================================================
# Automatically detects Linux distributions, BSD/macOS environments, and
# package managers to install required security CLI tools:
#   - nmap       (Network discovery and port scanner)
#   - gobuster   (URI and DNS brute-forcer)
#   - nikto      (Web vulnerability scanner + Perl XML writer)
#   - whois      (Domain and IP registration lookup)
#   - subfinder  (Fast passive subdomain enumeration)
# ==============================================================================

set -eo pipefail

# ANSI Color Codes
BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
RESET="\033[0m"

log_info()    { echo -e "${BLUE}[*]${RESET} $1"; }
log_success() { echo -e "${GREEN}[+]${RESET} $1"; }
log_warn()    { echo -e "${YELLOW}[!]${RESET} $1"; }
log_error()   { echo -e "${RED}[-]${RESET} $1"; }
log_header()  { echo -e "${BOLD}${CYAN}$1${RESET}"; }

SUBFINDER_VERSION="2.6.6"
INSTALL_USER_ONLY=false
CHECK_ONLY=false

usage() {
    cat <<EOF
Usage: ./scripts/install_deps.sh [OPTIONS]

Options:
  -c, --check       Verify installed tools and dependencies without modifying system.
  -u, --user        Install standalone binaries into \$HOME/.local/bin (no root/sudo needed).
  -h, --help        Show this help message.

Supported Environments:
  • Debian / Ubuntu / Kali / Parrot / Pop!_OS / Linux Mint (apt)
  • Arch Linux / Manjaro / EndeavourOS / BlackArch (pacman)
  • Fedora / RHEL / CentOS / Rocky / AlmaLinux (dnf / yum)
  • openSUSE Tumbleweed & Leap (zypper)
  • Alpine Linux (apk)
  • Void Linux (xbps)
  • macOS (Homebrew)
EOF
    exit 0
}

# Parse Command-Line Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--check)
            CHECK_ONLY=true
            shift
            ;;
        -u|--user)
            INSTALL_USER_ONLY=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

echo -e "${BOLD}======================================================${RESET}"
echo -e "${BOLD}${CYAN}   CyGuide System Dependency & Tool Installer${RESET}"
echo -e "${BOLD}======================================================${RESET}"

# Architecture & Platform Detection
UNAME_OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
UNAME_ARCH="$(uname -m)"

case "$UNAME_ARCH" in
    x86_64|amd64)   ARCH="amd64" ;;
    aarch64|arm64)  ARCH="arm64" ;;
    armv7*|armhf)   ARCH="armv7" ;;
    i386|i686)      ARCH="386" ;;
    *)              ARCH="amd64" ;;
esac

# Privilege Detection
SUDO=""
if [ "$INSTALL_USER_ONLY" = false ]; then
    if [ "$EUID" -ne 0 ]; then
        if command -v sudo >/dev/null 2>&1; then
            SUDO="sudo"
        else
            log_warn "Neither root nor sudo detected. Falling back to user-space binary installs."
            INSTALL_USER_ONLY=true
        fi
    fi
fi

# Binaries destination for standalone downloads
if [ "$INSTALL_USER_ONLY" = true ]; then
    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"
else
    BIN_DIR="/usr/local/bin"
fi

# Check Only Mode Handler
verify_tools() {
    echo ""
    log_header "--- Installed Security Tools Status ---"
    local all_good=true
    local tools=("nmap" "gobuster" "nikto" "whois" "subfinder")

    for tool in "${tools[@]}"; do
        if command -v "$tool" >/dev/null 2>&1; then
            local path
            path="$(command -v "$tool")"
            log_success "${BOLD}$tool${RESET} -> $path"
        else
            log_error "${BOLD}$tool${RESET} -> NOT FOUND"
            all_good=false
        fi
    done

    echo ""
    if [ "$all_good" = true ]; then
        log_success "All 5 core security tools are installed and ready!"
        log_info "Run ${BOLD}cyg check${RESET} to perform an end-to-end environment validation."
    else
        log_warn "Some tools are missing. Run ${BOLD}./scripts/install_deps.sh${RESET} to install them."
    fi
}

if [ "$CHECK_ONLY" = true ]; then
    verify_tools
    exit 0
fi

# Standalone Subfinder Binary Installer
install_subfinder_release() {
    if command -v subfinder >/dev/null 2>&1; then
        return 0
    fi

    log_info "Installing subfinder v${SUBFINDER_VERSION} binary for ${UNAME_OS}/${ARCH}..."
    local url="https://github.com/projectdiscovery/subfinder/releases/download/v${SUBFINDER_VERSION}/subfinder_${SUBFINDER_VERSION}_${UNAME_OS}_${ARCH}.zip"
    local tmp_dir
    tmp_dir="$(mktemp -d)"

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$url" -o "$tmp_dir/subfinder.zip" || {
            log_warn "Failed to download subfinder from $url. Please install manually."
            rm -rf "$tmp_dir"
            return 1
        }
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$url" -O "$tmp_dir/subfinder.zip" || {
            log_warn "Failed to download subfinder from $url. Please install manually."
            rm -rf "$tmp_dir"
            return 1
        }
    else
        log_warn "curl or wget is required to download standalone binaries."
        rm -rf "$tmp_dir"
        return 1
    fi

    if command -v unzip >/dev/null 2>&1; then
        unzip -q "$tmp_dir/subfinder.zip" -d "$tmp_dir"
        if [ "$INSTALL_USER_ONLY" = true ]; then
            mv "$tmp_dir/subfinder" "$BIN_DIR/subfinder"
            chmod +x "$BIN_DIR/subfinder"
        else
            $SUDO mv "$tmp_dir/subfinder" "$BIN_DIR/subfinder"
            $SUDO chmod +x "$BIN_DIR/subfinder"
        fi
        log_success "subfinder installed successfully to $BIN_DIR/subfinder"
    else
        log_warn "unzip is required to extract subfinder. Install unzip and re-run."
    fi

    rm -rf "$tmp_dir"
}

# Standalone Gobuster Binary Installer (Fallback for RHEL/openSUSE)
install_gobuster_release() {
    if command -v gobuster >/dev/null 2>&1; then
        return 0
    fi

    local GOBUSTER_VERSION="3.6.0"
    log_info "Installing gobuster v${GOBUSTER_VERSION} binary fallback for ${UNAME_OS}/${ARCH}..."
    local url="https://github.com/OJ/gobuster/releases/download/v${GOBUSTER_VERSION}/gobuster_${UNAME_OS}_${ARCH}.tar.gz"
    local tmp_dir
    tmp_dir="$(mktemp -d)"

    if curl -fsSL "$url" -o "$tmp_dir/gobuster.tar.gz" 2>/dev/null; then
        tar -xzf "$tmp_dir/gobuster.tar.gz" -C "$tmp_dir"
        if [ "$INSTALL_USER_ONLY" = true ]; then
            mv "$tmp_dir/gobuster" "$BIN_DIR/gobuster"
            chmod +x "$BIN_DIR/gobuster"
        else
            $SUDO mv "$tmp_dir/gobuster" "$BIN_DIR/gobuster"
            $SUDO chmod +x "$BIN_DIR/gobuster"
        fi
        log_success "gobuster installed successfully to $BIN_DIR/gobuster"
    else
        log_warn "Could not fetch pre-compiled gobuster binary."
    fi

    rm -rf "$tmp_dir"
}

# Detect Distribution and Package Manager
DISTRO="unknown"
if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    DISTRO="$ID"
    DISTRO_LIKE="${ID_LIKE:-$ID}"
fi

log_info "Detected OS: $UNAME_OS ($DISTRO / $UNAME_ARCH)"

# Package Manager Installation Logic
if command -v apt-get >/dev/null 2>&1; then
    log_info "Using APT package manager (Debian / Ubuntu / Kali / Parrot / Pop!_OS / Mint)..."
    $SUDO apt-get update -y

    # Core tools
    $SUDO apt-get install -y nmap whois libxml-writer-perl ca-certificates curl unzip

    # Gobuster
    if ! $SUDO apt-get install -y gobuster 2>/dev/null; then
        install_gobuster_release || true
    fi

    # Nikto
    $SUDO apt-get install -y nikto 2>/dev/null || {
        log_warn "nikto not found in apt repositories. You can install it via git clone."
    }

    # Subfinder (Standard in Kali/Parrot, external binary in Ubuntu/Debian)
    if ! $SUDO apt-get install -y subfinder 2>/dev/null; then
        log_info "subfinder not in default apt repos; downloading ProjectDiscovery release..."
        install_subfinder_release
    fi

elif command -v pacman >/dev/null 2>&1; then
    log_info "Using Pacman package manager (Arch Linux / Manjaro / EndeavourOS / BlackArch)..."
    $SUDO pacman -Sy --noconfirm --needed nmap whois perl-xml-writer curl ca-certificates unzip

    # Gobuster & Nikto
    $SUDO pacman -S --noconfirm --needed gobuster nikto 2>/dev/null || true

    # Subfinder
    if ! $SUDO pacman -S --noconfirm --needed subfinder 2>/dev/null; then
        if command -v yay >/dev/null 2>&1; then
            yay -S --noconfirm subfinder-bin || install_subfinder_release
        elif command -v paru >/dev/null 2>&1; then
            paru -S --noconfirm subfinder-bin || install_subfinder_release
        else
            install_subfinder_release
        fi
    fi

elif command -v dnf >/dev/null 2>&1; then
    log_info "Using DNF package manager (Fedora / RHEL / CentOS Stream / Rocky / AlmaLinux)..."
    $SUDO dnf install -y nmap whois perl-XML-Writer curl ca-certificates unzip tar

    # Try nikto & gobuster from repos/EPEL
    $SUDO dnf install -y nikto 2>/dev/null || log_warn "nikto may require EPEL repository on RHEL/CentOS."
    $SUDO dnf install -y gobuster 2>/dev/null || install_gobuster_release

    # Subfinder
    if ! $SUDO dnf install -y subfinder 2>/dev/null; then
        install_subfinder_release
    fi

elif command -v zypper >/dev/null 2>&1; then
    log_info "Using Zypper package manager (openSUSE Tumbleweed / Leap)..."
    $SUDO zypper --non-interactive install nmap whois perl-XML-Writer curl ca-certificates unzip tar

    $SUDO zypper --non-interactive install nikto 2>/dev/null || true
    $SUDO zypper --non-interactive install gobuster 2>/dev/null || install_gobuster_release
    install_subfinder_release

elif command -v apk >/dev/null 2>&1; then
    log_info "Using APK package manager (Alpine Linux)..."
    $SUDO apk add --no-cache nmap whois perl-xml-writer curl ca-certificates unzip

    $SUDO apk add --no-cache nikto 2>/dev/null || true
    $SUDO apk add --no-cache gobuster 2>/dev/null || install_gobuster_release
    $SUDO apk add --no-cache subfinder 2>/dev/null || install_subfinder_release

elif command -v xbps-install >/dev/null 2>&1; then
    log_info "Using XBPS package manager (Void Linux)..."
    $SUDO xbps-install -Sy nmap whois curl unzip ca-certificates
    $SUDO xbps-install -y gobuster 2>/dev/null || install_gobuster_release
    $SUDO xbps-install -y nikto 2>/dev/null || true
    install_subfinder_release

elif command -v brew >/dev/null 2>&1; then
    log_info "Using Homebrew (macOS / Linuxbrew)..."
    brew install nmap gobuster nikto whois subfinder

else
    log_warn "No recognized system package manager detected."
    log_info "Attempting standalone binary downloads into $BIN_DIR..."
    install_subfinder_release
    install_gobuster_release
fi

# Ensure user-level binary path is in PATH reminder
if [ "$INSTALL_USER_ONLY" = true ]; then
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo ""
        log_warn "Notice: $HOME/.local/bin is not in your current \$PATH."
        log_info "Add this to your ~/.bashrc or ~/.zshrc:"
        echo -e "    ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
    fi
fi

verify_tools
EOF
