#!/usr/bin/python3

import os
import tomllib
from typing import Any


def main():
    with open("./config.toml", "rb") as f:
        config = tomllib.load(f)
        process(config)


def process(config: dict[str, Any]):
    check_config(config)
    enable_ntp()
    setup_tmp_network(config)
    setup_keyring()
    format_partition(config)
    mount_partition(config)
    setup_system(config)
    pass


def check_config(config: dict[str, Any]):
    pass


def setup_keyring():
    os.system("pacman-key --init")
    os.system("pacman-key --populate")


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
    boot = config["partition"]["boot"]
    swap = config["partition"]["swap"]
    root = config["partition"]["root"]
    label = config["partition"]["label"]
    os.system(f"mkfs.fat -F32 {boot}")
    os.system(f"mkswap {swap}")
    os.system(f"mkfs.btrfs -fL {label} {root}")
    os.system(f"mount -t btrfs -o compress=zstd {root} /mnt")
    os.system("btrfs subvolume create /mnt/@")
    os.system("btrfs subvolume create /mnt/@home")
    os.system("umount /mnt")


def mount_partition(config: dict[str, Any]):
    boot = config["partition"]["boot"]
    swap = config["partition"]["swap"]
    root = config["partition"]["root"]
    os.system(f"mount -t btrfs -o subvol=/@,compress=zstd {root} /mnt")
    os.system("mkdir -p /mnt/home")
    os.system(f"mount -t btrfs -o subvol=/@home,compress=zstd {root} /mnt/home")
    os.system("mkdir -p /mnt/boot")
    os.system(f"mount {boot} /mnt/boot")
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


def setup_packages(config: dict[str, Any]):
    packages_: list[str] = config["os"]["packages"]
    packages = " ".join(packages_)
    os.system(f"pacstrap /mnt {packages}")


def setup_grub(config: dict[str, Any]):
    bootloader_id = config["grub"]["bootloader_id"]
    os.system(
        f"arch-chroot /mnt grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id={bootloader_id}"
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
    locale = multiline_str(config["os"]["locale"])
    append_file("/etc/locale.gen", locale)
    os.system("arch-chroot /mnt locale-gen")
    os.system(f"arch-chroot /mnt echo 'LANG={lang}' > /etc/locale.conf")


def setup_root():
    os.system("arch-chroot /mnt passwd root")


def setup_user(config: dict[str, Any]):
    username = config["user"]["name"]
    shell = config["user"]["shell"]
    os.system(f"arch-chroot /mnt useradd -m -G wheel -s /usr/bin/{shell} {username}")
    os.system(f"arch-chroot /mnt passwd {username}")
    os.system(
        "arch-chroot /mnt sed -i.bak '/^# %wheel ALL=(ALL:ALL) ALL/s/^# //' /etc/sudoers"
    )
    append_file("/mnt/etc/sudoers", "%wheel ALL=(ALL:ALL) ALL")


def setup_hosts(config: dict[str, Any]):
    hostname = config["os"]["hostname"]
    os.system(f"echo {hostname} > /mnt/etc/hostname")
    content = multiline_str(
        "127.0.0.1 localhost",
        "::1       localhost",
        f"127.0.1.1 {hostname}.localdomain {hostname}",
    )
    with open("/mnt/etc/hosts", "w") as f:
        f.write(content)


def setup_network(config: dict[str, Any]):
    if not config["network"]["reflector"]:
        os.system("arch-chroot /mnt systemctl stop reflector.service")
    mirrors: list[str] = [
        f"Server = {mirror}" for mirror in config["network"]["mirrors"]
    ]
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


# tool functions


def multiline_str(*s: str) -> str:
    return "\n".join(s)


def write_file(filename, content):
    with open(filename, "w") as f:
        f.write(content)


def append_file(filename, content):
    with open(filename, "a") as f:
        f.write(content)


if __name__ == "__main__":
    main()
