# -*- mode: ruby -*-
# vi: set ft=ruby :

# All Vagrant configuration is done below. The "2" in Vagrant.configure
# configures the configuration version (we support older styles for
# backwards compatibility). Please don't change it unless you know what
# you're doing.
Vagrant.configure(2) do |config|
  # The most common configuration options are documented and commented below.
  # For a complete reference, please see the online documentation at
  # https://docs.vagrantup.com.

  # Every Vagrant development environment requires a box. You can search for
  # boxes at https://atlas.hashicorp.com/search.
  config.vm.box = "ubuntu/trusty64"

  # Disable automatic box update checking. If you disable this, then
  # boxes will only be checked for updates when the user runs
  # `vagrant box outdated`. This is not recommended.
  # config.vm.box_check_update = false

  # Share an additional folder to the guest VM. The first argument is
  # the path on the host to the actual folder. The second argument is
  # the path on the guest to mount the folder. And the optional third
  # argument is a set of non-required options.
  # config.vm.synced_folder "../data", "/vagrant_data"

  config.vm.provider "virtualbox" do |vb|
  #   # Display the VirtualBox GUI when booting the machine
  #   vb.gui = true
  #
    # Customize the amount of memory on the VM:
    vb.memory = "2048"
  end

  # Enable provisioning with a shell script. Additional provisioners such as
  # Puppet, Chef, Ansible, Salt, and Docker are also available. Please see the
  # documentation for more information about their specific syntax and use.
  config.vm.provision "shell", inline: <<-SHELL
    sudo apt-get update
    sudo apt-get dist-upgrade -y
    sudo add-apt-repository ppa:gift/dev -y
    sudo apt-get update -q && sudo apt-get install -y ipython libbde-python libesedb-python libevt-python libevtx-python libewf-python libfwsi-python liblnk-python libmsiecf-python libolecf-python libqcow-python libregf-python libsigscan-python libsmdev-python libsmraw-python libtsk libvhdi-python libvmdk-python libvshadow-python python-artifacts python-bencode python-binplist python-construct python-dateutil python-dfvfs python-docopt python-dpkt python-hachoir-core python-hachoir-metadata python-hachoir-parser python-mock python-pefile python-protobuf python-psutil python-pyparsing python-requests python-six python-xlsxwriter python-yaml python-tz pytsk3 python-zmq
    sudo apt-get install -y python-pip && sudo pip install pylint
    sudo pip install ipython --upgrade
  SHELL

  # A Vagrant plugin that configures the virtual machine to use specified
  # proxies. This is useful for example in case you are behind a corporate
  # proxy server, or you have a caching proxy.
  # See https://github.com/tmatilai/vagrant-proxyconf for more info.
  # Install with:
  #   vagrant plugin install vagrant-proxyconf
  # Then uncomment the following lines to enable here, or place in
  # $HOME/.vagrant.d/Vagrantfile to enable for all Vagrant VMs
  #if Vagrant.has_plugin?("vagrant-proxyconf")
  #  config.proxy.http     = "http://192.168.0.2:3128/"
  #  config.proxy.https    = "http://192.168.0.2:3128/"
  #  config.proxy.no_proxy = "localhost,127.0.0.1,.example.com"
  #end

  # Share a common package cache among similiar VM instances, targetting
  # multiple package managers and Linux distros.
  # Install with:
  #   vagrant plugin install vagrant-cachier
  if Vagrant.has_plugin?("vagrant-cachier")
    config.cache.scope = :box
  end

  # Automatically install and keep up to date the host's VirtualBox Guest
  # Additions on the guest system.
  # Install with:
  #   vagrant plugin install vagrant-vbguest
  if Vagrant.has_plugin?("vagrant-vbguest")
    config.vbguest.auto_update = true
  end
end