{ config, pkgs, lib, ... }:

with lib;

let

  # Do the fetching and unpacking of the VirtualBox guest image
  # locally so that it works on non-Linux hosts.
  pkgsNative = import <nixpkgs> { system = builtins.currentSystem; };

  cfg = config.deployment.cloudsigma;

in

{

  ###### interface

  options = {

    deployment.cloudsigma.username = mkOption {
      default = "";
      type = types.str;
      description = ''
      '';
    };

    deployment.cloudsigma.password = mkOption {
      default = "";
      type = types.str;
      description = ''
      '';
    };

    deployment.cloudsigma.region = mkOption {
      default = "";
      example = "zrh";
      type = types.str;
      description = ''
      '';
    };

    deployment.cloudsigma.cpu = mkOption {
      default = 1000;
      type = types.int;
      description = ''
      '';
    };

    deployment.cloudsigma.ram = mkOption {
      default = 1000;
      type = types.int;
      description = ''
        Memory size (M) of virtual machine.
      '';
    };

    deployment.cloudsigma.disk = mkOption {
      default = 10000;
      type = types.int;
      description = ''
      '';
    };
  };


  ###### implementation

  config = mkIf (config.deployment.targetEnv == "cloudsigma") {
    nixpkgs.system = mkOverride 900 "x86_64-linux";
    fileSystems."/".device = "/dev/disk/by-label/nixos";

    boot.loader = {
      timeout = 1;
      grub.version = 2;
      grub.device = "/dev/vda";
    };
    services.openssh.enable = true;

    # Blacklist nvidiafb by default as it causes issues with some GPUs.
    boot.blacklistedKernelModules = [ "nvidiafb" ];

    security.initialRootPassword = mkDefault "!";
  };

}
