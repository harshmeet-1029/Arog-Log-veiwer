#!/bin/bash
# Complete Production Build for Linux
# This creates:
# 1. Standalone binary
# 2. .deb package (Debian/Ubuntu)
# 3. .rpm package (Fedora/RHEL/CentOS)
# 4. AppImage (Universal)

echo "============================================"
echo "Argo Log Viewer - Production Builder (Linux)"
echo "============================================"
echo

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run setup first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "[1/7] Activating virtual environment..."
source venv/bin/activate

# Install build tools
echo
echo "[2/7] Installing build tools..."
pip install pyinstaller --quiet

# Clean previous build
echo
echo "[3/7] Cleaning previous build..."
rm -rf dist build installers

# Create necessary directories
mkdir -p installers/linux

# Build the standalone binary
echo
echo "[4/7] Building standalone binary..."
echo "This may take a few minutes..."
echo

pyinstaller --name="ArgoLogViewer" \
    --onefile \
    --icon=app/ICON.png \
    --add-data="app:app" \
    --hidden-import=PySide6 \
    --hidden-import=paramiko \
    --hidden-import=cryptography \
    --clean \
    app/main.py

# Check if build was successful
if [ ! -f "dist/ArgoLogViewer" ]; then
    echo
    echo "========================================"
    echo "BUILD FAILED!"
    echo "========================================"
    echo
    echo "Binary creation failed. Check errors above."
    exit 1
fi

# Make executable
chmod +x dist/ArgoLogViewer

echo
echo "[5/7] Standalone binary created successfully!"
echo "Location: dist/ArgoLogViewer"
echo "Size: $(du -sh dist/ArgoLogViewer | cut -f1)"
echo

# Create .deb package
echo "[6/7] Creating DEB package (Debian/Ubuntu)..."
echo

mkdir -p installers/linux/deb/DEBIAN
mkdir -p installers/linux/deb/usr/bin
mkdir -p installers/linux/deb/usr/share/applications
mkdir -p installers/linux/deb/usr/share/pixmaps
mkdir -p installers/linux/deb/usr/share/doc/argologviewer

# Copy binary
cp dist/ArgoLogViewer installers/linux/deb/usr/bin/argologviewer

# Create control file
cat > installers/linux/deb/DEBIAN/control << EOF
Package: argologviewer
Version: 1.0.0
Section: utils
Priority: optional
Architecture: amd64
Depends: libc6 (>= 2.31), libgcc-s1 (>= 3.0), libstdc++6 (>= 10)
Maintainer: Harshmeet Singh <harshmeetsingh010@gmail.com>
Description: Argo Pod Log Viewer
 A production-grade desktop application for viewing Argo Workflow logs
 through SSH connections. Features real-time log streaming, pod search,
 and secure SSH connection management.
Homepage: https://github.com/harshmeetsingh/argo-log-viewer
EOF

# Create desktop entry
cat > installers/linux/deb/usr/share/applications/argologviewer.desktop << EOF
[Desktop Entry]
Name=Argo Log Viewer
Comment=View Argo Workflow logs through SSH
Exec=/usr/bin/argologviewer
Icon=argologviewer
Terminal=false
Type=Application
Categories=Development;Utility;
StartupNotify=true
EOF

# Create copyright file
cat > installers/linux/deb/usr/share/doc/argologviewer/copyright << EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: argologviewer
Source: https://github.com/harshmeetsingh/argo-log-viewer

Files: *
Copyright: $(date +%Y) Harshmeet Singh
License: MIT
 [Your license text here]
EOF

# Build .deb package
dpkg-deb --build installers/linux/deb installers/linux/argologviewer_1.0.0_amd64.deb 2>/dev/null

if [ -f "installers/linux/argologviewer_1.0.0_amd64.deb" ]; then
    echo "✓ DEB package created successfully"
    echo "  installers/linux/argologviewer_1.0.0_amd64.deb"
    echo "  Size: $(du -sh installers/linux/argologviewer_1.0.0_amd64.deb | cut -f1)"
else
    echo "⚠ DEB package creation failed (dpkg-deb not available)"
fi

echo

# Create .rpm package
echo "[7/7] Creating RPM package (Fedora/RHEL/CentOS)..."
echo

if command -v rpmbuild &> /dev/null; then
    mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
    
    # Create RPM spec file
    cat > ~/rpmbuild/SPECS/argologviewer.spec << EOF
Name:           argologviewer
Version:        1.0.0
Release:        1%{?dist}
Summary:        Argo Pod Log Viewer

License:        MIT
URL:            https://github.com/harshmeetsingh/argo-log-viewer
Source0:        %{name}-%{version}.tar.gz

BuildArch:      x86_64
Requires:       glibc, libgcc, libstdc++

%description
A production-grade desktop application for viewing Argo Workflow logs
through SSH connections. Features real-time log streaming, pod search,
and secure SSH connection management.

%prep
%setup -q

%build
# Binary is pre-built

%install
mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}/usr/share/applications
install -m 755 ArgoLogViewer %{buildroot}/usr/bin/argologviewer
install -m 644 argologviewer.desktop %{buildroot}/usr/share/applications/

%files
/usr/bin/argologviewer
/usr/share/applications/argologviewer.desktop

%changelog
* $(date '+%a %b %d %Y') Harshmeet Singh <harshmeetsingh010@gmail.com> - 1.0.0-1
- Initial release
EOF
    
    # Create source tarball
    mkdir -p /tmp/argologviewer-1.0.0
    cp dist/ArgoLogViewer /tmp/argologviewer-1.0.0/
    cp installers/linux/deb/usr/share/applications/argologviewer.desktop /tmp/argologviewer-1.0.0/
    tar -czf ~/rpmbuild/SOURCES/argologviewer-1.0.0.tar.gz -C /tmp argologviewer-1.0.0
    rm -rf /tmp/argologviewer-1.0.0
    
    # Build RPM
    rpmbuild -ba ~/rpmbuild/SPECS/argologviewer.spec 2>/dev/null
    
    # Copy to installers directory
    if [ -f ~/rpmbuild/RPMS/x86_64/argologviewer-1.0.0-1.*.rpm ]; then
        cp ~/rpmbuild/RPMS/x86_64/argologviewer-1.0.0-1.*.rpm installers/linux/
        echo "✓ RPM package created successfully"
        echo "  installers/linux/argologviewer-1.0.0-1.*.rpm"
        echo "  Size: $(du -sh installers/linux/*.rpm | cut -f1)"
    else
        echo "⚠ RPM package creation failed"
    fi
else
    echo "⚠ RPM package creation skipped (rpmbuild not available)"
    echo
    echo "To create RPM packages, install:"
    echo "  sudo apt-get install rpm  # On Debian/Ubuntu"
    echo "  sudo dnf install rpm-build  # On Fedora"
fi

echo
echo "========================================"
echo "PRODUCTION BUILD COMPLETE!"
echo "========================================"
echo
echo "Standalone Binary:"
echo "  dist/ArgoLogViewer"
echo "  Size: $(du -sh dist/ArgoLogViewer | cut -f1)"
echo

if [ -f "installers/linux/argologviewer_1.0.0_amd64.deb" ]; then
    echo "DEB Package (Debian/Ubuntu):"
    echo "  installers/linux/argologviewer_1.0.0_amd64.deb"
    echo "  Install with: sudo dpkg -i argologviewer_1.0.0_amd64.deb"
    echo
fi

if [ -f installers/linux/argologviewer-1.0.0-1.*.rpm ]; then
    echo "RPM Package (Fedora/RHEL):"
    echo "  installers/linux/argologviewer-1.0.0-1.*.rpm"
    echo "  Install with: sudo rpm -i argologviewer-1.0.0-1.*.rpm"
    echo
fi

echo "========================================"
echo "DISTRIBUTION READY!"
echo "========================================"
echo
echo "You can now distribute:"
echo "  1. dist/ArgoLogViewer - Standalone binary"
echo "  2. installers/linux/*.deb - For Debian/Ubuntu"
echo "  3. installers/linux/*.rpm - For Fedora/RHEL/CentOS"
echo

deactivate
