# compiler-rt builtins for the clang/lld driven ucrtarm64 target, which has
# no libgcc.  Builtins only; the sanitizers and profile runtimes are not
# usable on this target yet.
#
# LLVM publishes no per-project tarballs, and the builtins CMakeLists reaches
# outside its own directory (third-party/siphash), so Source0 is the full
# monorepo and only compiler-rt/lib/builtins is configured.

# Only the LLVM based target needs compiler-rt; the GCC targets use libgcc.
%global mingw_build_win32     0
%global mingw_build_win64     0
%global mingw_build_ucrt64    0
%global mingw_build_ucrtarm64 1

Name:           mingw-compiler-rt
Version:        22.1.8
Release:        1%{?dist}
Summary:        MinGW cross-compiled LLVM compiler runtime

License:        Apache-2.0 WITH LLVM-exception OR NCSA
URL:            https://compiler-rt.llvm.org/
Source0:        https://github.com/llvm/llvm-project/releases/download/llvmorg-%{version}/llvm-project-%{version}.src.tar.xz

BuildArch:      noarch

# clang's resource directory is versioned by clang's major version only, so
# derive it from %%{version}.  %%build asserts that this matches the clang in
# the buildroot -- if it ever drifts, the driver would silently stop finding
# the builtins.
%global clang_major      %(echo %{version} | cut -d. -f1)
%global clang_next       %{lua: print(math.floor(tonumber(rpm.expand("%{clang_major}")) + 1))}
%global clang_resource   %{_prefix}/lib/clang/%{clang_major}

# The runtime directory name is clang's normalised form of the
# aarch64-w64-mingw32 triple, not the triple itself.
%global ucrtarm64_rt_triple  aarch64-w64-windows-gnu
%global ucrtarm64_rt_dir     %{clang_resource}/lib/%{ucrtarm64_rt_triple}

BuildRequires:  clang
BuildRequires:  cmake
BuildRequires:  lld
BuildRequires:  llvm
BuildRequires:  ninja-build
BuildRequires:  clang-resource-filesystem >= %{clang_major}
BuildRequires:  clang-resource-filesystem <  %{clang_next}
BuildRequires:  ucrtarm64-filesystem >= 152
BuildRequires:  ucrtarm64-headers
BuildRequires:  ucrtarm64-crt
BuildRequires:  ucrtarm64-clang

# The archive holds aarch64 PE/COFF objects, which the host BRP strip passes
# silently corrupt (the ar symbol index is lost).  %%mingw_package_header does
# not help here: this is the only package in the stack installing outside the
# sysroot, into clang's resource directory, so nil the passes outright.
%global __brp_strip                 %{nil}
%global __brp_strip_lto             %{nil}
%global __brp_strip_static_archive  %{nil}
%global __brp_strip_comment_note    %{nil}
%global __brp_llvm_compile_lto_elf  %{nil}
%global debug_package               %{nil}

%description
LLVM compiler runtime (builtins) cross-compiled for MinGW targets.

The aarch64-w64-mingw32 target has no libgcc, as it is driven by clang and
lld rather than by GCC, so the compiler runtime comes from compiler-rt
instead.


%package -n ucrtarm64-compiler-rt
Summary:        LLVM compiler runtime for the Windows on ARM64 target
Requires:       ucrtarm64-filesystem >= 152
Requires:       ucrtarm64-crt
Requires:       clang-resource-filesystem >= %{clang_major}
Requires:       clang-resource-filesystem <  %{clang_next}

%description -n ucrtarm64-compiler-rt
LLVM compiler runtime (builtins) for the aarch64-w64-mingw32 target.

This is the low level runtime library the compiler emits calls to for
operations the hardware does not implement directly (128 bit integer
arithmetic, soft float, outline atomics, __chkstk).  It is what
-rtlib=compiler-rt links against, in place of the libgcc that the GCC based
MinGW targets use.


%prep
%autosetup -n llvm-project-%{version}.src


%build
# The resource directory this package installs into must be the one the clang
# in the buildroot actually searches.
test "%{clang_major}" = "%{clang_major_version}"

# rpm exports the host x86_64 build flags, and cmake would pick them up from
# the environment.  None of them are valid for aarch64-w64-windows-gnu
# (-march=x86-64, -mtls-dialect=, the annobin specs files, ...), so build with
# nothing but what cmake derives from CMAKE_BUILD_TYPE.
unset CFLAGS CXXFLAGS FFLAGS FCFLAGS CPPFLAGS LDFLAGS ASFLAGS

# NB. deliberately no %%ucrtarm64_cmake here.  This is the only package in the
# stack that installs outside the sysroot, and %%ucrtarm64_cmake hardcodes
# -DCMAKE_INSTALL_PREFIX=%%{ucrtarm64_prefix} (plus the libdir/includedir
# overrides), which fights the clang resource directory this has to land in.
#
# Nothing can be linked until these builtins exist, so cmake's compiler check
# is kept to compiling a static library; the aarch64-w64-mingw32-clang driver
# always passes -rtlib=compiler-rt, and there is nothing yet for it to find.
mkdir -p _build
cd _build
cmake -G Ninja ../compiler-rt/lib/builtins \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_SYSTEM_NAME=Windows \
    -DCMAKE_C_COMPILER=%{ucrtarm64_target}-clang \
    -DCMAKE_CXX_COMPILER=%{ucrtarm64_target}-clang++ \
    -DCMAKE_ASM_COMPILER=%{ucrtarm64_target}-clang \
    -DCMAKE_C_COMPILER_TARGET=%{ucrtarm64_rt_triple} \
    -DCMAKE_CXX_COMPILER_TARGET=%{ucrtarm64_rt_triple} \
    -DCMAKE_ASM_COMPILER_TARGET=%{ucrtarm64_rt_triple} \
    -DCMAKE_C_COMPILER_WORKS=1 \
    -DCMAKE_CXX_COMPILER_WORKS=1 \
    -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY \
    -DCMAKE_AR=%{_bindir}/llvm-ar \
    -DCMAKE_RANLIB=%{_bindir}/llvm-ranlib \
    -DCMAKE_FIND_ROOT_PATH=%{ucrtarm64_prefix} \
    -DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=ONLY \
    -DCMAKE_INSTALL_PREFIX=%{clang_resource} \
    -DLLVM_ENABLE_PER_TARGET_RUNTIME_DIR=ON \
    -DCOMPILER_RT_DEFAULT_TARGET_ONLY=TRUE \
    -DCOMPILER_RT_USE_BUILTINS_LIBRARY=TRUE \
    -DCOMPILER_RT_EXCLUDE_ATOMIC_BUILTIN=FALSE
ninja -v


%install
cd _build
DESTDIR=%{buildroot} ninja install
cd ..

# Normalise whatever layout the install target produced onto the single path
# the clang driver searches for this target, so that %%files can name it
# exactly rather than glob it.
mkdir -p %{buildroot}%{ucrtarm64_rt_dir}
lib=$(find %{buildroot} -type f -name 'libclang_rt.builtins*.a')
# Exactly one archive: a second match would be silently deleted below.
test -n "$lib"
test "$(echo "$lib" | wc -l)" = 1
if [ "$lib" != "%{buildroot}%{ucrtarm64_rt_dir}/libclang_rt.builtins.a" ] ; then
    mv "$lib" %{buildroot}%{ucrtarm64_rt_dir}/libclang_rt.builtins.a
fi
find %{buildroot} -type f ! -path '%{buildroot}%{ucrtarm64_rt_dir}/libclang_rt.builtins.a' -delete
find %{buildroot} -depth -type d -empty -delete

# Belt and braces: re-index the archive with the LLVM ranlib, so that anything
# which rewrote it above (or any host tool that does not understand aarch64
# PE/COFF) cannot leave it without a usable ar symbol index.  %%check verifies
# the index afterwards, and runs after the buildroot policy scripts.
llvm-ranlib %{buildroot}%{ucrtarm64_rt_dir}/libclang_rt.builtins.a


%check
rtlib=%{buildroot}%{ucrtarm64_rt_dir}/libclang_rt.builtins.a

# 1. The driver must look for the builtins exactly where they were installed.
# -print-runtime-dir cannot be used for this: it refuses to print a directory
# that does not exist yet, and this package is what creates it.  Reassemble the
# same path from the resource directory and the normalised target triple
# instead.  clang reports the resource dir relative to its own location
# (/usr/bin/../lib/clang/22), so canonicalise it before comparing.
resourcedir=$(readlink -m "$(%{ucrtarm64_target}-clang -print-resource-dir)")
triple=$(%{ucrtarm64_target}-clang -print-target-triple)
echo "resource dir: $resourcedir  target triple: $triple"
%{ucrtarm64_target}-clang -print-runtime-dir || :
test "$resourcedir/lib/$triple" = "%{ucrtarm64_rt_dir}"

# 2. The ar symbol index must be intact.  %%check runs after the buildroot
# policy scripts, so this is what actually catches a stripper having eaten it.
#
# A GNU style archive carries the symbol table as its first member, named "/";
# the first ten bytes are therefore "!<arch>\n" followed by "/ ".  A corrupted,
# index-less archive starts with the long name table "//" instead.
header=$(od -A n -t x1 -N 10 "$rtlib" | tr -d ' \n')
echo "archive header bytes: $header"
test "$header" = "213c617263683e0a2f20"

# 3. ... and the index must actually resolve: llvm-nm --print-armap lists the
# index entries as "<symbol> in <member>".
llvm-nm --print-armap "$rtlib" | grep -q '^__chkstk in ' || \
    { echo "ar symbol index does not resolve __chkstk" ; exit 1 ; }
llvm-nm --print-armap "$rtlib" | grep -q '^__aarch64_cas4_relax in ' || \
    { echo "ar symbol index does not resolve __aarch64_cas4_relax" ; exit 1 ; }

# 4/5. Generic 128 bit integer helpers, the aarch64 outline atomics and the
# Windows stack probe must all be defined.  __chkstk in particular is only
# built when cmake detected a MinGW target, not a bare metal one.
for sym in __udivti3 __umodti3 __divti3 __ashlti3 __aarch64_cas4_relax \
           __aarch64_ldadd8_acq_rel __chkstk ; do
    llvm-nm --defined-only "$rtlib" | grep -qw "$sym" || \
        { echo "missing expected symbol: $sym" ; exit 1 ; }
done

# 6. The cross compiler must still be able to compile against the packaged
# headers.
printf '#include <stdio.h>\nint ucrtarm64_smoke(void) { return 0; }\n' | \
    %{ucrtarm64_target}-clang -c -x c -o /dev/null -

# 7. Member count sanity.
echo "archive members: $(llvm-ar t "$rtlib" | wc -l)"
test "$(llvm-ar t "$rtlib" | wc -l)" -ge 250

# 8. And the point of the whole package: a real link.  Point clang at a
# resource directory assembled out of the buildroot copy of the builtins and
# the stock clang builtin headers, so -rtlib=compiler-rt (which the driver
# always passes) resolves against what is about to be shipped.  -unwindlib=none
# because libunwind is not packaged yet -- flags after the driver name win.
rdir=$(pwd)/_resourcedir
rm -rf "$rdir"
mkdir -p "$rdir/lib"
ln -s %{clang_resource}/include "$rdir/include"
ln -s %{buildroot}%{ucrtarm64_rt_dir} "$rdir/lib/%{ucrtarm64_rt_triple}"

cat > _linktest.c <<'EOF'
__attribute__((noinline)) unsigned __int128 divmod(unsigned __int128 a,
                                                   unsigned __int128 b)
{
    return (a / b) + (a % b);
}

int main(void)
{
    /* Large enough to force a __chkstk stack probe. */
    volatile char probe[70000];
    probe[0] = 1;
    return (int)divmod(0x123456789abcdef0ULL, 3) + probe[0];
}
EOF
%{ucrtarm64_target}-clang -resource-dir "$rdir" -unwindlib=none \
    -o _linktest.exe _linktest.c
llvm-objdump -f _linktest.exe
llvm-objdump -f _linktest.exe | grep -q 'coff-arm64'

# 9. Negative control, so that 8 cannot pass vacuously: the same link against
# an empty resource directory must fail, which is what proves the builtins
# archive is what satisfied __chkstk and the 128 bit helpers.
mkdir -p _emptyresourcedir/lib
if %{ucrtarm64_target}-clang -resource-dir "$(pwd)/_emptyresourcedir" \
       -unwindlib=none -o _negative.exe _linktest.c 2>_negative.log ; then
    echo "linked without the builtins: the link test above proves nothing"
    exit 1
fi
echo "negative control failed as expected:"
cat _negative.log


%files -n ucrtarm64-compiler-rt
%license compiler-rt/LICENSE.TXT
%doc compiler-rt/CREDITS.TXT compiler-rt/README.txt
%dir %{ucrtarm64_rt_dir}
%{ucrtarm64_rt_dir}/libclang_rt.builtins.a


%changelog
* Thu Aug 06 2026 Erik Berg <fedora@slipsprogrammor.no> - 22.1.8-1
- Initial package: compiler-rt builtins for aarch64-w64-mingw32 (ucrtarm64)
- Version tracks the clang shipped by Fedora, since the builtins are installed
  into clang's own resource directory
