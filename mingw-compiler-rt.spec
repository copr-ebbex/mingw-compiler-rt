# compiler-rt builtins for the clang/lld driven MinGW targets.  Builtins
# only; the sanitizers and profile runtimes are not usable on these targets
# yet.
#
# ucrtarm64 has no libgcc at all.  win32 and win64 have one, but their clang
# supplement drivers (mingw32-clang, mingw64-clang) select the LLVM runtime
# stack, so they need the builtins too.  ucrt64 is deliberately absent: its
# normalised triple is the same as win64's (x86_64-w64-windows-gnu), so the
# win64 archive already serves it; a future ucrt64-compiler-rt is a matter of
# dependencies, not of a second build.
#
# LLVM publishes no per-project tarballs, and the builtins CMakeLists reaches
# outside its own directory (third-party/siphash), so Source0 is the full
# monorepo and only compiler-rt/lib/builtins is configured.

# The targets built, and the toolchain build flags for the mingw macros.
%global rt_targets aarch64-w64-mingw32 i686-w64-mingw32 x86_64-w64-mingw32
%global mingw_build_win32     1
%global mingw_build_win64     1
%global mingw_build_ucrt64    0
%global mingw_build_ucrtarm64 1

Name:           mingw-compiler-rt
Version:        22.1.8
Release:        2%{?dist}
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

# The runtime directory names are clang's normalised forms of the triples,
# not the triples themselves.
%global ucrtarm64_rt_triple  aarch64-w64-windows-gnu
%global ucrtarm64_rt_dir     %{clang_resource}/lib/%{ucrtarm64_rt_triple}
%global win32_rt_triple      i686-w64-windows-gnu
%global win32_rt_dir         %{clang_resource}/lib/%{win32_rt_triple}
%global win64_rt_triple      x86_64-w64-windows-gnu
%global win64_rt_dir         %{clang_resource}/lib/%{win64_rt_triple}

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
BuildRequires:  mingw32-filesystem >= 152
BuildRequires:  mingw32-headers
BuildRequires:  mingw32-crt
BuildRequires:  mingw32-clang
BuildRequires:  mingw64-filesystem >= 152
BuildRequires:  mingw64-headers
BuildRequires:  mingw64-crt
BuildRequires:  mingw64-clang

# The ucrtarm64 archive holds aarch64 PE/COFF objects, which the host BRP
# strip passes silently corrupt (the ar symbol index is lost).
# %%mingw_package_header does not help here: this is the only package in the
# stack installing outside the sysroot, into clang's resource directory, so
# nil the passes outright.
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
instead.  The win32 and win64 targets have clang supplement drivers which
select the same runtime stack.


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


%package -n mingw32-compiler-rt
Summary:        LLVM compiler runtime for the win32 target
Requires:       mingw32-filesystem >= 152
Requires:       mingw32-crt
Requires:       clang-resource-filesystem >= %{clang_major}
Requires:       clang-resource-filesystem <  %{clang_next}

%description -n mingw32-compiler-rt
LLVM compiler runtime (builtins) for the i686-w64-mingw32 target.

It is what -rtlib=compiler-rt links against when the mingw32-clang
supplement drivers are used in place of the GCC toolchain and its libgcc.


%package -n mingw64-compiler-rt
Summary:        LLVM compiler runtime for the win64 target
Requires:       mingw64-filesystem >= 152
Requires:       mingw64-crt
Requires:       clang-resource-filesystem >= %{clang_major}
Requires:       clang-resource-filesystem <  %{clang_next}

%description -n mingw64-compiler-rt
LLVM compiler runtime (builtins) for the x86_64-w64-mingw32 target.

It is what -rtlib=compiler-rt links against when the mingw64-clang
supplement drivers are used in place of the GCC toolchain and its libgcc.
The archive also serves a future ucrt64 clang toolchain: both triples
normalise to x86_64-w64-windows-gnu, and the builtins do not touch the CRT.


%prep
%autosetup -n llvm-project-%{version}.src


%build
# The resource directory this package installs into must be the one the clang
# in the buildroot actually searches.
test "%{clang_major}" = "%{clang_major_version}"

# rpm exports the host x86_64 build flags, and cmake would pick them up from
# the environment.  None of them are valid for the cross targets
# (-mtls-dialect=, the annobin specs files, ...), so build with nothing but
# what cmake derives from CMAKE_BUILD_TYPE.
unset CFLAGS CXXFLAGS FFLAGS FCFLAGS CPPFLAGS LDFLAGS ASFLAGS

# NB. deliberately no %%<target>_cmake here.  This is the only package in the
# stack that installs outside the sysroot, and those macros hardcode
# -DCMAKE_INSTALL_PREFIX=<sysroot> (plus the libdir/includedir overrides),
# which fights the clang resource directory this has to land in.
#
# Nothing can be linked until these builtins exist, so cmake's compiler check
# is kept to compiling a static library; the <triplet>-clang drivers always
# pass -rtlib=compiler-rt, and there is nothing yet for them to find.
for target in %{rt_targets}; do
  rt_triple=$(echo $target | sed 's/-mingw32$/-windows-gnu/')
  sysroot=%{_prefix}/$target/sys-root/mingw
  mkdir -p _build-$target
  cd _build-$target
  cmake -G Ninja ../compiler-rt/lib/builtins \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_SYSTEM_NAME=Windows \
      -DCMAKE_C_COMPILER=$target-clang \
      -DCMAKE_CXX_COMPILER=$target-clang++ \
      -DCMAKE_ASM_COMPILER=$target-clang \
      -DCMAKE_C_COMPILER_TARGET=$rt_triple \
      -DCMAKE_CXX_COMPILER_TARGET=$rt_triple \
      -DCMAKE_ASM_COMPILER_TARGET=$rt_triple \
      -DCMAKE_C_COMPILER_WORKS=1 \
      -DCMAKE_CXX_COMPILER_WORKS=1 \
      -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY \
      -DCMAKE_AR=%{_bindir}/llvm-ar \
      -DCMAKE_RANLIB=%{_bindir}/llvm-ranlib \
      -DCMAKE_FIND_ROOT_PATH=$sysroot \
      -DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=ONLY \
      -DCMAKE_INSTALL_PREFIX=%{clang_resource} \
      -DLLVM_ENABLE_PER_TARGET_RUNTIME_DIR=ON \
      -DCOMPILER_RT_DEFAULT_TARGET_ONLY=TRUE \
      -DCOMPILER_RT_USE_BUILTINS_LIBRARY=TRUE \
      -DCOMPILER_RT_EXCLUDE_ATOMIC_BUILTIN=FALSE
  ninja -v
  cd ..
done


%install
# Install each target into its own scratch DESTDIR, then place the single
# archive it produced onto the exact path the clang driver searches, so that
# %%files can name it rather than glob it.
for target in %{rt_targets}; do
  rt_triple=$(echo $target | sed 's/-mingw32$/-windows-gnu/')
  rt_dir=%{clang_resource}/lib/$rt_triple
  cd _build-$target
  DESTDIR=$(pwd)/../_inst-$target ninja install
  cd ..
  lib=$(find _inst-$target -type f -name 'libclang_rt.builtins*.a')
  # Exactly one archive: a second match would mean this loop hides output.
  test -n "$lib"
  test "$(echo "$lib" | wc -l)" = 1
  install -D -m 0644 "$lib" %{buildroot}$rt_dir/libclang_rt.builtins.a

  # Belt and braces: re-index the archive with the LLVM ranlib, so that
  # anything which rewrote it above (or any host tool that does not
  # understand aarch64 PE/COFF) cannot leave it without a usable ar symbol
  # index.  %%check verifies the index afterwards, and runs after the
  # buildroot policy scripts.
  llvm-ranlib %{buildroot}$rt_dir/libclang_rt.builtins.a
done


%check
for target in %{rt_targets}; do
  rt_triple=$(echo $target | sed 's/-mingw32$/-windows-gnu/')
  rt_dir=%{clang_resource}/lib/$rt_triple
  rtlib=%{buildroot}$rt_dir/libclang_rt.builtins.a

  # Per-target expectations.  i686 PE symbols carry a leading underscore, and
  # a 32 bit target has 64 bit division helpers where the 64 bit targets have
  # 128 bit ones.  The armap probe is a symbol the index must resolve; the
  # object format is what the link test's exe must identify as.
  case $target in
    aarch64-*)
      syms="__udivti3 __umodti3 __divti3 __ashlti3 __aarch64_cas4_relax __aarch64_ldadd8_acq_rel __chkstk"
      armap_sym=__chkstk
      objformat=coff-arm64
      members_min=250
      ;;
    i686-*)
      syms="___udivdi3 ___umoddi3 ___divdi3 ___ashldi3"
      armap_sym=___udivdi3
      objformat=coff-i386
      members_min=120
      ;;
    x86_64-*)
      syms="__udivti3 __umodti3 __divti3 __ashlti3"
      armap_sym=__udivti3
      objformat=coff-x86-64
      members_min=120
      ;;
  esac

  # 1. The driver must look for the builtins exactly where they were
  # installed.  -print-runtime-dir cannot be used for this: it refuses to
  # print a directory that does not exist yet, and this package is what
  # creates it.  Reassemble the same path from the resource directory and the
  # normalised target triple instead.  clang reports the resource dir
  # relative to its own location (/usr/bin/../lib/clang/22), so canonicalise
  # it before comparing.
  resourcedir=$(readlink -m "$($target-clang -print-resource-dir)")
  triple=$($target-clang -print-target-triple)
  echo "$target: resource dir: $resourcedir  target triple: $triple"
  test "$resourcedir/lib/$triple" = "$rt_dir"

  # 2. The ar symbol index must be intact.  %%check runs after the buildroot
  # policy scripts, so this is what actually catches a stripper having eaten
  # it.
  #
  # A GNU style archive carries the symbol table as its first member, named
  # "/"; the first ten bytes are therefore "!<arch>\n" followed by "/ ".  A
  # corrupted, index-less archive starts with the long name table "//"
  # instead.
  header=$(od -A n -t x1 -N 10 "$rtlib" | tr -d ' \n')
  echo "$target: archive header bytes: $header"
  test "$header" = "213c617263683e0a2f20"

  # 3. ... and the index must actually resolve: llvm-nm --print-armap lists
  # the index entries as "<symbol> in <member>".
  llvm-nm --print-armap "$rtlib" | grep -q "^$armap_sym in " || \
      { echo "$target: ar symbol index does not resolve $armap_sym" ; exit 1 ; }

  # 4/5. The division helpers (and on aarch64 the outline atomics and the
  # Windows stack probe) must all be defined.  The stack probes for the x86
  # targets are exercised by the link test below instead of being named here:
  # their spellings vary across compiler-rt releases, while the emitted call
  # either resolves or the link fails.
  for sym in $syms ; do
      llvm-nm --defined-only "$rtlib" | grep -qw "$sym" || \
          { echo "$target: missing expected symbol: $sym" ; exit 1 ; }
  done

  # 6. The cross compiler must still be able to compile against the packaged
  # headers.
  printf '#include <stdio.h>\nint mingw_rt_smoke(void) { return 0; }\n' | \
      $target-clang -c -x c -o /dev/null -

  # 7. Member count sanity.  aarch64 carries the outline atomics on top of
  # the generic set, so its floor is higher.
  echo "$target: archive members: $(llvm-ar t "$rtlib" | wc -l)"
  test "$(llvm-ar t "$rtlib" | wc -l)" -ge $members_min

  # 8. And the point of the whole package: a real link.  Point clang at a
  # resource directory assembled out of the buildroot copy of the builtins
  # and the stock clang builtin headers, so -rtlib=compiler-rt (which the
  # drivers always pass) resolves against what is about to be shipped.
  # -unwindlib=none because libunwind is not necessarily packaged yet for
  # this target -- flags after the driver name win.  The wide division picks
  # up the 128 bit helpers where int128 exists and the 64 bit ones on i686;
  # the oversized stack frame forces a stack probe on every arch.
  rdir=$(pwd)/_resourcedir-$target
  rm -rf "$rdir"
  mkdir -p "$rdir/lib"
  ln -s %{clang_resource}/include "$rdir/include"
  ln -s %{buildroot}$rt_dir "$rdir/lib/$rt_triple"

  cat > _linktest.c <<'EOF'
#ifdef __SIZEOF_INT128__
typedef unsigned __int128 wide;
#else
typedef unsigned long long wide;
#endif

__attribute__((noinline)) wide divmod(wide a, wide b)
{
    return (a / b) + (a % b);
}

int main(void)
{
    /* Large enough to force a stack probe. */
    volatile char probe[70000];
    probe[0] = 1;
    return (int)divmod(0x123456789abcdef0ULL, 3) + probe[0];
}
EOF
  $target-clang -resource-dir "$rdir" -unwindlib=none \
      -o _linktest-$target.exe _linktest.c
  llvm-objdump -f _linktest-$target.exe
  llvm-objdump -f _linktest-$target.exe | grep -q "$objformat"

  # 9. Negative control, so that 8 cannot pass vacuously: the same link
  # against an empty resource directory must fail, which is what proves the
  # builtins archive is what satisfied the stack probe and the division
  # helpers.
  mkdir -p _emptyresourcedir/lib
  if $target-clang -resource-dir "$(pwd)/_emptyresourcedir" \
         -unwindlib=none -o _negative-$target.exe _linktest.c 2>_negative.log ; then
      echo "$target: linked without the builtins: the link test above proves nothing"
      exit 1
  fi
  echo "$target: negative control failed as expected:"
  cat _negative.log
done


%files -n ucrtarm64-compiler-rt
%license compiler-rt/LICENSE.TXT
%doc compiler-rt/CREDITS.TXT compiler-rt/README.txt
%dir %{ucrtarm64_rt_dir}
%{ucrtarm64_rt_dir}/libclang_rt.builtins.a

%files -n mingw32-compiler-rt
%license compiler-rt/LICENSE.TXT
%doc compiler-rt/CREDITS.TXT compiler-rt/README.txt
%dir %{win32_rt_dir}
%{win32_rt_dir}/libclang_rt.builtins.a

%files -n mingw64-compiler-rt
%license compiler-rt/LICENSE.TXT
%doc compiler-rt/CREDITS.TXT compiler-rt/README.txt
%dir %{win64_rt_dir}
%{win64_rt_dir}/libclang_rt.builtins.a


%changelog
* Mon Aug 24 2026 Erik Berg <fedora@slipsprogrammor.no> - 22.1.8-2
- Add the win32 and win64 builtins for the mingw32-clang and mingw64-clang
  supplement drivers, installed per normalised triple; the win64 archive is
  also what a future ucrt64 clang toolchain will use, as both triples
  normalise to x86_64-w64-windows-gnu
- Per-target link tests replace the single-target ones; the x86 stack probe
  spellings are proven by linking rather than named

* Thu Aug 06 2026 Erik Berg <fedora@slipsprogrammor.no> - 22.1.8-1
- Initial package: compiler-rt builtins for aarch64-w64-mingw32 (ucrtarm64)
- Version tracks the clang shipped by Fedora, since the builtins are installed
  into clang's own resource directory
