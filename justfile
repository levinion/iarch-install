set dotenv-path:="config.env"
set dotenv-required
set shell:=["bash","-c"]

install:
  @just enable-ntp
  @just set-partition
  @just mount-partition
  @just install-system
  @just install-ucode
  @just install-grub
  @just gen-fstab
  @just set-hosts
  @just set-timezone
  @just set-locale
  @just set-root-password
  @just set-pacman
  @just enable-networkmanager
  @just add-user
  @just change-root
  @just umount-all

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
  pacstrap /mnt base base-devel linux linux-firmware btrfs-progs networkmanager vim sudo git $shell

install-ucode:
  #!/usr/bin/bash
  if [[ "$ucode" == "intel" ]]; then
  pacstrap /mnt intel-ucode
  elif [[ "$ucode" == "amd" ]]; then
  pacstrap /mnt amd-ucode
  else
  echo "only support intel or amd";
  fi

install-grub:
  pacstrap /mnt grub efibootmgr os-prober
  arch-chroot /mnt grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=$bootloader_id
  arch-chroot /mnt vim /etc/default/grub
  arch-chroot /mnt grub-mkconfig -o /boot/grub/grub.cfg

gen-fstab:
  genfstab -U /mnt > /mnt/etc/fstab

change-root:
  arch-chroot /mnt

set-hosts:
  #!/usr/bin/bash
  arch-chroot /mnt echo $hostname > /etc/hostname
  cat > /mnt/etc/hosts << EOF
  127.0.0.1 localhost
  ::1       localhost
  127.0.1.1 $hostname.localdomain $hostname
  EOF

set-timezone:
  arch-chroot /mnt ln -sf /usr/share/zoneinfo/$timezone /etc/localtime
  arch-chroot /mnt hwclock --systohc

set-locale:
  arch-chroot /mnt vim /etc/locale.gen
  arch-chroot /mnt locale-gen
  arch-chroot /mnt echo 'LANG=en_US.UTF-8'  > /etc/locale.conf

set-root-password:
  arch-chroot /mnt passwd root

add-user:
  arch-chroot /mnt useradd -m -G wheel -s usr/bin/$shell $username
  arch-chroot /mnt passwd user
  arch-chroot /mnt sed -i.bak '/^# %wheel ALL=(ALL:ALL) ALL/s/^# //' /etc/sudoers

set-pacman:
  vim /mnt/etc/pacman.conf

enable-networkmanager:
  arch-chroot /mnt systemctl enable NetworkManager.service --now

end-of-basic-installation:
  #!/usr/bin/bash
  echo "Basic installation done..."
  echo ""
  read -rp "Do you'd like to install i3 with sddm? [y/n]" ctn
  if [[ "$ctn" == "n" ]]; then
    echo "Bye, $username. Just enjoy yourself.";
  else
    pacstrap /mnt i3-wm sddm
    arch-chroot /mnt systemctl enable sddm.service --now
  fi

i3:
  arch-chroot /mnt
