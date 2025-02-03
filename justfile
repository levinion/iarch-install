set dotenv-path:="config.env"
set dotenv-required
set shell:=["bash","-c"]

install:
  @just enable-ntp
  @just set-partition
  @just mount-partition
  @just install-system
  @just gen-fstab
  @just change-root
  @just set-hosts
  @just set-timezone
  @just set-locale
  @just set-root-password
  @just install-ucode
  @just install-grub
  @just ready-for-reboot

enable-ntp:
  timedatectl set-ntp true

set-partition:
  mkfs.fat -F32 $boot
  mkswap $swap
  mkfs.btrfs -fL $partition_label $root
  mount -t btrfs -o compress=zstd $root /mnt
  btrfs subvolume create /mnt/@
  btrfs subvolume create /mnt/@home
  umount /mnt

mount-partition:
  mount -t btrfs -o subvol=/@,compress=zstd $root /mnt
  mkdir -p /mnt/home
  mount -t btrfs -o subvol=/@home,compress=zstd $root /mnt/home
  mkdir -p /mnt/boot
  mount $boot /mnt/boot
  swapon $swap

install-system:
  pacman -S archlinux-keyring
  pacstrap /mnt base base-devel linux linux-firmware btrfs-progs networkmanager vim sudo $shell

gen-fstab:
  genfstab -U /mnt > /mnt/etc/fstab

change-root:
  arch-chroot /mnt

set-hosts:
  echo $hostname > /etc/hostname
  echo > /etc/hosts <<EOF
  127.0.0.1 localhost
  ::1       localhost
  127.0.1.1 $hostname.localdomain $hostname
  EOF

set-timezone:
  ln -sf /usr/share/zoneinfo/$timezone /etc/localtime
  hwclock --systohc

set-locale:
  vim /etc/locale.gen
  locale-gen
  echo 'LANG=en_US.UTF-8'  > /etc/locale.conf

set-root-password:
  passwd root

install-ucode:
  if [[ "$ucode" -eq "intel" ]]; then
  pacman -S intel-ucode
  elif [[ "$ucode" -eq "amd" ]]; then
  pacman -S amd-ucode
  else
  echo "only support intel or amd";
  fi

install-grub:
  pacman -S grub efibootmgr os-prober
  grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=$bootloader_id
  vim /etc/default/grub
  grub-mkconfig -o /boot/grub/grub.cfg

ready-for-reboot:
  exit
  umount -R /mnt
  reboot
