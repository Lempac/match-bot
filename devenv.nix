{ pkgs, lib, config, inputs, ... }:

{
  env.SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
  containers."match-bot" = {
    name = "match-bot";
    startupCommand = config.processes.serve.exec;
  };
  processes.serve.exec = "python main.py";
  packages = [
      pkgs.python312Packages.discordpy
      pkgs.python312Packages.python-dotenv
      pkgs.sqlite
  ];
  languages.python.enable = true;
  # languages.python.venv.enable = true;
}
