#!/bin/bash
# Build the smooth-text Tk for FT Assistant's own Python on Linux. Run by hand; no GitHub automation.
#
#   bash installer/build-smooth-tk.sh            -> dist/<SMOOTH_TK_FILE>, and its SHA-256
#
# Why: the Python runtime setup downloads (python-build-standalone) has a Tk that draws with old
# X11 fonts, so the setup window's text is rough. Tk is a separate library in that runtime
# (python/lib/libtcl9tk9.0.so), so we build the same Tk version with smooth fonts (Xft) and setup
# swaps it in before any window opens.
#
# When the runtime pinned in installer/install.py (RUNTIME_RELEASE / RUNTIME_PYTHON) changes:
#   1. set SMOOTH_TK_VERSION in install.py to the new runtime's Tk version (this script checks);
#   2. run this script; it prints the new file's SHA-256 for SMOOTH_TK_SHA256 in install.py;
#   3. upload the file to a new GitHub release, tagged smooth-tk-<version> and marked as a
#      pre-release (so the app's update check, which reads the latest release, never sees it):
#        gh release create smooth-tk-<version> dist/<file> --prerelease --title ... --notes ...
#
# Nothing is installed on this computer: the header files it needs (Xft, fontconfig, freetype)
# are downloaded as packages with apt-get download and unpacked into the work folder.
# Needs: gcc, make, curl, Debian/Ubuntu/Mint (apt-get download), and libXft/libfontconfig/X11
# libraries (any desktop has them).
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
pin() { sed -n "s/^$1 = \"\(.*\)\".*/\1/p" "$REPO/installer/install.py" | head -n 1; }
RELEASE="$(pin RUNTIME_RELEASE)"; PY="$(pin RUNTIME_PYTHON)"; TK="$(pin SMOOTH_TK_VERSION)"
OUT_NAME="$(pin SMOOTH_TK_FILE)"
[ -n "$RELEASE" ] && [ -n "$PY" ] && [ -n "$TK" ] && [ -n "$OUT_NAME" ] || { echo "Pins not found in install.py" >&2; exit 1; }
WORK="${WORK:-$(mktemp -d)}"
OUT="$REPO/dist/$OUT_NAME"
TCLV="$TK"            # Tcl and Tk share version numbers in the runtimes we use (checked below)
echo "Runtime cpython-$PY+$RELEASE, Tk $TK; working in $WORK"
cd "$WORK"

# 1. The pinned runtime, to check its Tk version and test the result.
TARBALL="cpython-$PY+$RELEASE-x86_64-unknown-linux-gnu-install_only.tar.gz"
[ -f "$TARBALL" ] || curl -fL --progress-bar -o "$TARBALL" \
  "https://github.com/astral-sh/python-build-standalone/releases/download/$RELEASE/${TARBALL//+/%2B}"
rm -rf runtime && mkdir runtime && tar -xzf "$TARBALL" -C runtime
HAVE="$(runtime/python/bin/python3 -I -c 'import tkinter; t = tkinter.Tcl(); print(t.call("info", "patchlevel"))')"
[ "$HAVE" = "$TK" ] || { echo "The runtime has Tcl/Tk $HAVE, but SMOOTH_TK_VERSION is $TK." >&2; exit 1; }
[ -f runtime/python/lib/libtcl9tk9.0.so ] || { echo "The runtime has no lib/libtcl9tk9.0.so; the layout changed." >&2; exit 1; }

# 2. Header files, unpacked here only.
mkdir -p debs sysroot && (cd debs && apt-get download libxft-dev libfontconfig-dev libfreetype-dev >/dev/null)
for d in debs/*.deb; do dpkg-deb -x "$d" sysroot; done
LIB="$WORK/sysroot/usr/lib/x86_64-linux-gnu"
rm -f "$LIB"/*.a
for l in libXft.so.2 libfontconfig.so.1 libfreetype.so.6; do       # link against this system's
  ln -sf "/lib/x86_64-linux-gnu/$l" "$LIB/${l%.*}"                  # libraries (.so -> .so.N)
done
mkdir -p bin && cat > bin/xft-config <<EOF
#!/bin/sh
case "\$1" in
  --cflags) echo "-I$WORK/sysroot/usr/include -I$WORK/sysroot/usr/include/freetype2";;
  --libs) echo "-L$LIB -lXft -lfontconfig";;
esac
EOF
chmod +x bin/xft-config
# Use the oldest versions of these math functions, so the library also loads on older Linux
# (glibc 2.29-2.38 gave them new symbol versions without changing how they're called).
cat > oldglibc.h <<'EOF'
__asm__(".symver pow,pow@GLIBC_2.2.5");
__asm__(".symver fmod,fmod@GLIBC_2.2.5");
__asm__(".symver fmodf,fmodf@GLIBC_2.2.5");
__asm__(".symver hypot,hypot@GLIBC_2.2.5");
EOF

# 3. Tcl (only for building Tk against), then Tk with smooth fonts.
SF="https://downloads.sourceforge.net/project/tcl/Tcl/$TCLV"
for n in "tcl$TCLV" "tk$TK"; do
  [ -f "$n-src.tar.gz" ] || curl -fsSL -o "$n-src.tar.gz" "$SF/$n-src.tar.gz"
  rm -rf "$n" && tar -xzf "$n-src.tar.gz"
done
(cd "tcl$TCLV/unix" && ./configure --enable-64bit --disable-zipfs >../../tcl.log 2>&1 \
   && make -j"$(nproc)" binaries >>../../tcl.log 2>&1) || { echo "Tcl build failed: $WORK/tcl.log" >&2; exit 1; }
(cd "tk$TK/unix" && PATH="$WORK/bin:$PATH" CFLAGS="-O2 -include $WORK/oldglibc.h" \
   ./configure --with-tcl="$WORK/tcl$TCLV/unix" --enable-64bit --enable-xft --disable-xss \
   --disable-zipfs >../../tk.log 2>&1 && PATH="$WORK/bin:$PATH" make -j"$(nproc)" >>../../tk.log 2>&1) \
  || { echo "Tk build failed: $WORK/tk.log" >&2; exit 1; }
grep -q "checking whether to use xft... yes" tk.log || { echo "Tk was built without Xft." >&2; exit 1; }
BUILT="tk$TK/unix/libtcl9tk9.0.so"

# 4. Checks: only common desktop libraries, nothing newer than glibc 2.14, and smooth fonts.
NEEDS="$(readelf -d "$BUILT" | sed -n 's/.*Shared library: \[\(.*\)\]/\1/p' | sort | tr '\n' ' ')"
echo "Needs: $NEEDS"
for l in $NEEDS; do
  case "$l" in libXft.so.2|libfontconfig.so.1|libX11.so.6|libm.so.6|libc.so.6) ;;
    *) echo "Unexpected library $l" >&2; exit 1;; esac
done
NEWEST="$(objdump -T "$BUILT" | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -n 1)"
echo "Newest glibc symbol: $NEWEST"
[ "$(printf '%s\nGLIBC_2.14\n' "$NEWEST" | sort -V | tail -n 1)" = "GLIBC_2.14" ] \
  || { echo "Needs a newer glibc than 2.14." >&2; exit 1; }
strip --strip-unneeded "$BUILT"
cp "$BUILT" runtime/python/lib/libtcl9tk9.0.so
FS="$(runtime/python/bin/python3 -I -c 'import tkinter; r = tkinter.Tk(); r.withdraw(); print(r.tk.call("::tk::pkgconfig", "get", "fontsystem"))')"
[ "$FS" = "xft" ] || { echo "The built Tk doesn't draw with smooth fonts ($FS)." >&2; exit 1; }

mkdir -p "$REPO/dist"
cp "$BUILT" "$OUT"
echo "Built $OUT ($(stat -c %s "$OUT") bytes)"
echo "SMOOTH_TK_SHA256 = \"$(sha256sum "$OUT" | cut -d' ' -f1)\""
