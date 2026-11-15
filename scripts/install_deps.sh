#!/usr/bin/env bash
# ==============================================================================
# CyGuide Universal Dependency & Tool Installer
# ==============================================================================
# Automatically detects Linux distributions, BSD/macOS environments, and
# package managers to install required security CLI tools and dependencies:
#   - nmap         (Network discovery and port scanner)
#   - gobuster     (URI and DNS brute-forcer)
#   - nikto        (Web vulnerability scanner + Perl XML writer)
#   - whois        (Domain and IP registration lookup)
#   - subfinder    (Fast passive subdomain enumeration)
#   - ffuf         (Fast web fuzzer and directory discovery)
#   - nuclei       (Fast and customizable vulnerability scanner)
#   - searchsploit (Offline exploit search engine for Exploit-DB)
#   - dnspython    (Pure-Python DNS resolver and zone transfer engine)
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
FFUF_VERSION="2.1.0"
NUCLEI_VERSION="3.3.7"
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
    local tools=("nmap" "gobuster" "nikto" "whois" "subfinder" "ffuf" "nuclei" "searchsploit")

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

    # Check Pure-Python dnspython dependency
    if python3 -c "import dns.resolver" >/dev/null 2>&1; then
        log_success "${BOLD}dnspython${RESET} -> python3 module available"
    else
        log_warn "${BOLD}dnspython${RESET} -> NOT FOUND (install via 'pip install dnspython')"
        all_good=false
    fi

    echo ""
    if [ "$all_good" = true ]; then
        log_success "All 9 security tools and adapters are installed and ready!"
        log_info "Run ${BOLD}cyg check${RESET} to perform an end-to-end environment validation."
    else
        log_warn "Some tools are missing. Run ${BOLD}./scripts/install_deps.sh${RESET} to install them."
    fi
}

if [ "$CHECK_ONLY" = true ]; then
    verify_tools
    exit 0
fi

# Helper function to download file via curl or wget
download_file() {
    local url="$1"
    local output="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$url" -o "$output"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$url" -O "$output"
    else
        log_warn "curl or wget is required to download standalone binaries."
        return 1
    fi
}

# Standalone Subfinder Binary Installer
install_subfinder_release() {
    if command -v subfinder >/dev/null 2>&1; then
        return 0
    fi

    log_info "Installing subfinder v${SUBFINDER_VERSION} binary for ${UNAME_OS}/${ARCH}..."
    local url="https://github.com/projectdiscovery/subfinder/releases/download/v${SUBFINDER_VERSION}/subfinder_${SUBFINDER_VERSION}_${UNAME_OS}_${ARCH}.zip"
    local tmp_dir
    tmp_dir="$(mktemp -d)"

    if download_file "$url" "$tmp_dir/subfinder.zip"; then
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
    else
        log_warn "Failed to download subfinder from $url. Please install manually."
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

    if download_file "$url" "$tmp_dir/gobuster.tar.gz"; then
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

# Standalone FFUF Binary Installer
install_ffuf_release() {
    if command -v ffuf >/dev/null 2>&1; then
        return 0
    fi

    log_info "Installing ffuf v${FFUF_VERSION} binary for ${UNAME_OS}/${ARCH}..."
    local url="https://github.com/ffuf/ffuf/releases/download/v${FFUF_VERSION}/ffuf_${FFUF_VERSION}_${UNAME_OS}_${ARCH}.tar.gz"
    local tmp_dir
    tmp_dir="$(mktemp -d)"

    if download_file "$url" "$tmp_dir/ffuf.tar.gz"; then
        tar -xzf "$tmp_dir/ffuf.tar.gz" -C "$tmp_dir"
        if [ "$INSTALL_USER_ONLY" = true ]; then
            mv "$tmp_dir/ffuf" "$BIN_DIR/ffuf"
            chmod +x "$BIN_DIR/ffuf"
        else
            $SUDO mv "$tmp_dir/ffuf" "$BIN_DIR/ffuf"
            $SUDO chmod +x "$BIN_DIR/ffuf"
        fi
        log_success "ffuf installed successfully to $BIN_DIR/ffuf"
    else
        log_warn "Could not fetch pre-compiled ffuf binary."
    fi

    rm -rf "$tmp_dir"
}

# Standalone Nuclei Binary Installer
install_nuclei_release() {
    if command -v nuclei >/dev/null 2>&1; then
        return 0
    fi

    log_info "Installing nuclei v${NUCLEI_VERSION} binary for ${UNAME_OS}/${ARCH}..."
    local url="https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_${UNAME_OS}_${ARCH}.zip"
    local tmp_dir
    tmp_dir="$(mktemp -d)"

    if download_file "$url" "$tmp_dir/nuclei.zip"; then
        if command -v unzip >/dev/null 2>&1; then
            unzip -q "$tmp_dir/nuclei.zip" -d "$tmp_dir"
            if [ "$INSTALL_USER_ONLY" = true ]; then
                mv "$tmp_dir/nuclei" "$BIN_DIR/nuclei"
                chmod +x "$BIN_DIR/nuclei"
            else
                $SUDO mv "$tmp_dir/nuclei" "$BIN_DIR/nuclei"
                $SUDO chmod +x "$BIN_DIR/nuclei"
            fi
            log_success "nuclei installed successfully to $BIN_DIR/nuclei"
        else
            log_warn "unzip is required to extract nuclei. Install unzip and re-run."
        fi
    else
        log_warn "Failed to download nuclei from $url. Please install manually."
    fi

    rm -rf "$tmp_dir"
}

# Standalone SearchSploit (Exploit-DB) Installer
install_searchsploit() {
    if command -v searchsploit >/dev/null 2>&1; then
        return 0
    fi

    log_info "Installing searchsploit (Exploit-DB)..."
    local target_dir
    if [ "$INSTALL_USER_ONLY" = true ]; then
        target_dir="$HOME/.local/share/exploitdb"
    else
        target_dir="/opt/exploitdb"
    fi

    if command -v git >/dev/null 2>&1; then
        if [ ! -d "$target_dir" ]; then
            if [ "$INSTALL_USER_ONLY" = true ]; then
                git clone --depth 1 https://gitlab.com/exploit-database/exploitdb.git "$target_dir" 2>/dev/null || \
                git clone --depth 1 https://github.com/offensive-security/exploitdb.git "$target_dir" 2>/dev/null || true
            else
                $SUDO git clone --depth 1 https://gitlab.com/exploit-database/exploitdb.git "$target_dir" 2>/dev/null || \
                $SUDO git clone --depth 1 https://github.com/offensive-security/exploitdb.git "$target_dir" 2>/dev/null || true
            fi
        fi

        if [ -f "$target_dir/searchsploit" ]; then
            if [ "$INSTALL_USER_ONLY" = true ]; then
                ln -sf "$target_dir/searchsploit" "$BIN_DIR/searchsploit"
                chmod +x "$BIN_DIR/searchsploit"
            else
                $SUDO ln -sf "$target_dir/searchsploit" "$BIN_DIR/searchsploit"
                $SUDO chmod +x "$BIN_DIR/searchsploit"
            fi
            log_success "searchsploit installed successfully to $BIN_DIR/searchsploit"
            return 0
        fi
    fi
    log_warn "Could not automatically install searchsploit. Install exploitdb package manually."
    return 1
}

# Python Dependencies Installer
install_python_deps() {
    if ! python3 -c "import dns.resolver" >/dev/null 2>&1; then
        log_info "Installing pure-Python dependency dnspython..."
        if command -v pip3 >/dev/null 2>&1; then
            pip3 install --quiet dnspython 2>/dev/null || true
        elif command -v python3 >/dev/null 2>&1; then
            python3 -m pip install --quiet dnspython 2>/dev/null || true
        fi
    fi
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
    $SUDO apt-get install -y nmap whois libxml-writer-perl ca-certificates curl unzip tar git

    # Gobuster
    if ! $SUDO apt-get install -y gobuster 2>/dev/null; then
        install_gobuster_release || true
    fi

    # Nikto
    $SUDO apt-get install -y nikto 2>/dev/null || {
        log_warn "nikto not found in apt repositories. You can install it via git clone."
    }

    # Subfinder
    if ! $SUDO apt-get install -y subfinder 2>/dev/null; then
        install_subfinder_release || true
    fi

    # FFUF
    if ! $SUDO apt-get install -y ffuf 2>/dev/null; then
        install_ffuf_release || true
    fi

    # Nuclei
    if ! $SUDO apt-get install -y nuclei 2>/dev/null; then
        install_nuclei_release || true
    fi

    # SearchSploit (Exploit-DB)
    if ! $SUDO apt-get install -y exploitdb 2>/dev/null; then
        install_searchsploit || true
    fi

    install_python_deps

elif command -v pacman >/dev/null 2>&1; then
    log_info "Using Pacman package manager (Arch Linux / Manjaro / EndeavourOS / BlackArch)..."
    $SUDO pacman -Sy --noconfirm --needed nmap whois perl-xml-writer curl ca-certificates unzip tar git

    # Gobuster, Nikto, FFUF
    $SUDO pacman -S --noconfirm --needed gobuster nikto ffuf 2>/dev/null || true

    # Subfinder
    if ! $SUDO pacman -S --noconfirm --needed subfinder 2>/dev/null; then
        if command -v yay >/dev/null 2>&1; then
            yay -S --noconfirm subfinder-bin || install_subfinder_release || true
        elif command -v paru >/dev/null 2>&1; then
            paru -S --noconfirm subfinder-bin || install_subfinder_release || true
        else
            install_subfinder_release || true
        fi
    fi

    # Nuclei
    if ! $SUDO pacman -S --noconfirm --needed nuclei 2>/dev/null; then
        if command -v yay >/dev/null 2>&1; then
            yay -S --noconfirm nuclei-bin || install_nuclei_release || true
        elif command -v paru >/dev/null 2>&1; then
            paru -S --noconfirm nuclei-bin || install_nuclei_release || true
        else
            install_nuclei_release || true
        fi
    fi

    # Exploit-DB / SearchSploit
    if ! $SUDO pacman -S --noconfirm --needed exploitdb 2>/dev/null; then
        install_searchsploit || true
    fi

    install_python_deps

elif command -v dnf >/dev/null 2>&1; then
    log_info "Using DNF package manager (Fedora / RHEL / CentOS Stream / Rocky / AlmaLinux)..."
    $SUDO dnf install -y nmap whois perl-XML-Writer curl ca-certificates unzip tar git

    $SUDO dnf install -y nikto 2>/dev/null || log_warn "nikto may require EPEL repository on RHEL/CentOS."
    $SUDO dnf install -y gobuster 2>/dev/null || install_gobuster_release || true
    $SUDO dnf install -y ffuf 2>/dev/null || install_ffuf_release || true

    if ! $SUDO dnf install -y subfinder 2>/dev/null; then
        install_subfinder_release || true
    fi
    if ! $SUDO dnf install -y nuclei 2>/dev/null; then
        install_nuclei_release || true
    fi
    if ! $SUDO dnf install -y exploitdb 2>/dev/null; then
        install_searchsploit || true
    fi

    install_python_deps

elif command -v zypper >/dev/null 2>&1; then
    log_info "Using Zypper package manager (openSUSE Tumbleweed / Leap)..."
    $SUDO zypper --non-interactive install nmap whois perl-XML-Writer curl ca-certificates unzip tar git

    $SUDO zypper --non-interactive install nikto 2>/dev/null || true
    $SUDO zypper --non-interactive install gobuster 2>/dev/null || install_gobuster_release || true
    $SUDO zypper --non-interactive install ffuf 2>/dev/null || install_ffuf_release || true
    install_subfinder_release || true
    install_nuclei_release || true
    install_searchsploit || true
    install_python_deps

elif command -v apk >/dev/null 2>&1; then
    log_info "Using APK package manager (Alpine Linux)..."
    $SUDO apk add --no-cache nmap whois perl-xml-writer curl ca-certificates unzip tar git

    $SUDO apk add --no-cache nikto 2>/dev/null || true
    $SUDO apk add --no-cache gobuster 2>/dev/null || install_gobuster_release || true
    $SUDO apk add --no-cache ffuf 2>/dev/null || install_ffuf_release || true
    $SUDO apk add --no-cache subfinder 2>/dev/null || install_subfinder_release || true
    install_nuclei_release || true
    install_searchsploit || true
    install_python_deps

elif command -v xbps-install >/dev/null 2>&1; then
    log_info "Using XBPS package manager (Void Linux)..."
    $SUDO xbps-install -Sy nmap whois curl unzip ca-certificates tar git
    $SUDO xbps-install -y gobuster 2>/dev/null || install_gobuster_release || true
    $SUDO xbps-install -y nikto 2>/dev/null || true
    $SUDO xbps-install -y ffuf 2>/dev/null || install_ffuf_release || true
    install_subfinder_release || true
    install_nuclei_release || true
    install_searchsploit || true
    install_python_deps

elif command -v brew >/dev/null 2>&1; then
    log_info "Using Homebrew (macOS / Linuxbrew)..."
    brew install nmap gobuster nikto whois subfinder ffuf nuclei exploitdb
    install_python_deps

else
    log_warn "No recognized system package manager detected."
    log_info "Attempting standalone binary downloads into $BIN_DIR..."
    install_subfinder_release || true
    install_gobuster_release || true
    install_ffuf_release || true
    install_nuclei_release || true
    install_searchsploit || true
    install_python_deps
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
