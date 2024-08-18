let
  pkgs = import <nixpkgs> {};
in pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (python-pkgs: [
      python-pkgs.mido
      python-pkgs.evdev
      python-pkgs.pulsectl
      python-pkgs.python-rtmidi
      python-pkgs.debugpy
    ]))
  ];
}
