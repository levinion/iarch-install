#!/usr/bin/python3

import os
import tomllib
from typing import Any
import argparse


def read_config():
    with open("./config.toml", "rb") as f:
        config = tomllib.load(f)
        return config


def main():
    config = read_config()
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "install",
        help="Execute the installation process based on the config.toml file in the current directory.",
    )
    subparsers.add_parser(
        "mount", help="Mount disks according to the configuration file."
    )
    args = parser.parse_args()
    match args.command:
        case "mount":
            mount_partition(config)
        case "install":
            install(config)
        case _:
            parser.print_help()


def install(config: dict[str, Any]):
    check_config(config)
    enable_ntp()
    setup_tmp_network(config)
    format_partition(config)
    mount_partition(config)
    setup_system(config)
    umount()
    complete_hint()


def complete_hint():
    print(
        "Installation is done. Now you could reboot and load to your desktop. Don't forget to install archlinuxcn-keyring if you are using archlinuxcn."
    )


def check_config(config: dict[str, Any]):
    if (
        not config["grub"]["disable_os_prober"]
        and "os-prober" not in config["os"]["packages"]
    ):
        print(
            "[CONFIG_ERROR] grub.disable_os_prober is false, but os-prober is not included in os.packages."
        )
        exit(1)


def enable_ntp():
    os.system("timedatectl set-ntp true")


def setup_tmp_network(config: dict[str, Any]):
    if not config["network"]["reflector"]:
        os.system("systemctl stop reflector.service")
    mirrors: list[str] = [
        f"Server = {mirror}" for mirror in config["network"]["mirrors"]
    ]
    write_file("/etc/pacman.d/mirrorlist", multiline_str(*mirrors))


def format_partition(config: dict[str, Any]):
    efi = config["partition"]["efi"]
    enable_swap = config["partition"]["enable_swap"]
    swap = ""
    if enable_swap:
        swap = config["partition"]["swap"]
    root = config["partition"]["root"]
    label = config["partition"]["label"]
    compress = config["partition"]["compress"]
    os.system(f"mkfs.fat -F32 {efi}")
    if enable_swap:
        os.system(f"mkswap {swap}")
    os.system(f"mkfs.btrfs -fL {label} {root}")
    os.system(f"mount -t btrfs -o compress={compress} {root} /mnt")
    os.system("btrfs subvolume create /mnt/@")
    os.system("btrfs subvolume create /mnt/@home")
    os.system("btrfs subvolume create /mnt/@snapshots")
    os.system("umount /mnt")


def mount_partition(config: dict[str, Any]):
    efi = config["partition"]["efi"]
    swap = ""
    enable_swap = config["partition"]["enable_swap"]
    if enable_swap:
        swap = config["partition"]["swap"]
    root = config["partition"]["root"]
    compress = config["partition"]["compress"]
    os.system(f"mount -t btrfs -o subvol=/@,compress={compress} {root} /mnt")
    os.system("mkdir -p /mnt/home")
    os.system(f"mount -t btrfs -o subvol=/@home,compress={compress} {root} /mnt/home")
    os.system("mkdir -p /mnt/snapshots")
    os.system(
        f"mount -t btrfs -o subvol=/@snapshots,compress={compress} {root} /mnt/snapshots"
    )
    os.system("mkdir -p /mnt/efi")
    os.system(f"mount {efi} /mnt/efi")
    if enable_swap:
        os.system(f"swapon {swap}")


def setup_system(config: dict[str, Any]):
    setup_packages(config)
    setup_grub(config)
    gen_fstab()
    setup_timezone(config)
    setup_locale(config)
    setup_hosts(config)
    setup_pacman(config)
    setup_network(config)
    setup_root()
    setup_user(config)
    enable_services(config)


def setup_packages(config: dict[str, Any]):
    packages_: list[str] = config["os"]["packages"]
    if config["user"]["shell"] not in packages_:
        packages_.append(config["user"]["shell"])
    packages = " ".join(packages_)
    os.system(f"pacstrap /mnt {packages}")


def setup_grub(config: dict[str, Any]):
    bootloader_id = config["grub"]["bootloader_id"]
    os.system(
        f"arch-chroot /mnt grub-install --target=x86_64-efi --efi-directory=/efi --bootloader-id={bootloader_id}"
    )
    if not config["grub"]["disable_os_prober"]:
        append_file("/mnt/etc/default/grub", "GRUB_DISABLE_OS_PROBER=false")
    os.system("arch-chroot /mnt grub-mkconfig -o /boot/grub/grub.cfg")


def gen_fstab():
    os.system("genfstab -U /mnt > /mnt/etc/fstab")


def setup_timezone(config: dict[str, Any]):
    timezone = config["os"]["timezone"]
    os.system(f"arch-chroot /mnt ln -sf /usr/share/zoneinfo/{timezone} /etc/localtime")
    os.system("arch-chroot /mnt hwclock --systohc")


def setup_locale(config: dict[str, Any]):
    lang = config["os"]["lang"]
    locale = multiline_str(*config["os"]["locale"])
    append_file("/mnt/etc/locale.gen", locale)
    os.system("arch-chroot /mnt locale-gen")
    write_file("/mnt/etc/locale.conf", f"LANG={lang}")


def setup_root():
    print("password for root: ")
    os.system("arch-chroot /mnt passwd root")


def setup_user(config: dict[str, Any]):
    username = config["user"]["name"]
    shell = config["user"]["shell"]
    os.system(f"arch-chroot /mnt useradd -m -G wheel -s /usr/bin/{shell} {username}")
    print(f"password for {username}: ")
    os.system(f"arch-chroot /mnt passwd {username}")
    append_file("/mnt/etc/sudoers", "%wheel ALL=(ALL:ALL) ALL")


def setup_hosts(config: dict[str, Any]):
    hostname = config["os"]["hostname"]
    os.system(f"echo {hostname} > /mnt/etc/hostname")
    content = multiline_str(
        "127.0.0.1 localhost",
        "::1       localhost",
        f"127.0.1.1 {hostname}.localdomain {hostname}",
    )
    write_file("/mnt/etc/hosts", content)


def setup_network(config: dict[str, Any]):
    if not config["network"]["reflector"]:
        os.system("arch-chroot /mnt systemctl stop reflector.service")
    mirrors: list[str] = [
        f"Server = {mirror}" for mirror in config["network"]["mirrors"]
    ]
    if len(mirrors) != 0:
        write_file("/mnt/etc/pacman.d/mirrorlist", multiline_str(*mirrors))


def setup_pacman(config: dict[str, Any]):
    if config["pacman"]["multilib"]:
        enable_multilib()
    if config["pacman"]["archlinuxcn"]:
        enable_archlinuxcn()


def enable_multilib():
    content = multiline_str("[multilib]", "Include = /etc/pacman.d/mirrorlist")
    append_file("/mnt/etc/pacman.conf", content)


def enable_archlinuxcn():
    content = multiline_str(
        "[archlinuxcn]", "Server = https://repo.archlinuxcn.org/$arch"
    )
    append_file("/mnt/etc/pacman.conf", content)


def enable_services(config: dict[str, Any]):
    for service in config["os"]["enabled_services"]:
        os.system(f"arch-chroot /mnt systemctl enable {service}")


def umount():
    os.system("umount -R /mnt")


# tool functions


def multiline_str(*s: str) -> str:
    return "\n".join(s) + "\n"


def write_file(filename, content):
    with open(filename, "w") as f:
        f.write(content)


def append_file(filename, content):
    with open(filename, "a") as f:
        f.write(content)


if __name__ == "__main__":
    main()
