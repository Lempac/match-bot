{ pkgs, lib, config, inputs, ... }:

{
  containers."match-bot" = {
    name = "match-bot";
    startupCommand = config.processes.serve.exec;
  };
  processes.serve.exec = "python main.py";
  packages = [
      pkgs.python312Packages.discordpy
      pkgs.python312Packages.python-dotenv
      pkgs.sqlite
      pkgs.openssl
  ];
  languages.python.enable = true;
  # languages.python.venv.enable = true;
}
