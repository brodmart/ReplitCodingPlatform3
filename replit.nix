{pkgs}: {
  deps = [
    pkgs.redis
    pkgs.rabbitmq-server
    pkgs.icu
    pkgs.dotnet-sdk
    pkgs.iana-etc
    pkgs.glibcLocales
    pkgs.lsof
    pkgs.gcc
    pkgs.mono
    pkgs.postgresql
    pkgs.openssl
  ];
}
