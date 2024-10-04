{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };

  outputs = { self, nixpkgs }:
  let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
  in
  {
    devShell.${system} = pkgs.mkShell{
        packages = [
            (pkgs.python3.withPackages (py: [
              py.discordpy
              py.python-dotenv
            ]))
            pkgs.sqlite
            pkgs.nodejs_20
        ];
    };
  };
}
