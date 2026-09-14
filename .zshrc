
export ZSH="/home/admin/.oh-my-zsh"
export PATH="$PATH:/bin:/usr/bin"

# VS Codium Flatpak Fixes
if [[ "$TERM_PROGRAM" == "vscodium" ]]; then
  export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"
  alias sudo='sudo -S'  
  if command -v direnv &> /dev/null; then
    eval "$(direnv hook zsh)"
  fi
fi

if [[ "$TERM_PROGRAM" == "vscode" || -n "$VSCODE_INJECTION" ]]; then
    unset GIO_MODULE_DIR
    unset GTK_MODULES
    unset GTK_IM_MODULE
fi

# Docker "Nuke" Function
dkr() {
    if [ -z "$1" ]; then
        echo "Usage: dkr <name>"
    else
        echo "Stopping, removing, and deleting image for: $1..."
        docker stop "$1" 2>/dev/null && \
        docker rm "$1" 2>/dev/null && \
        docker rmi "$1"
    fi
}

ZSH_THEME="robbyrussell"

if command -v direnv >/dev/null 2>&1; then
  eval "$(direnv hook zsh)"
fi

COMPLETION_WAITING_DOTS="true"

plugins=(
   git
   zsh-autosuggestions
   )

source $ZSH/oh-my-zsh.sh

alias python=/usr/bin/python3.12
alias python3=/usr/bin/python3.12
alias pip=pip3
alias kitten='kitty +kitten'

# ~/.zshrc: your interactive zsh startup

# 1) Only run for interactive shells
[[ $- != *i* ]] && return

# 2) PATH
export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"

# Keep __pycache__ out of the stowed (symlinked) config dirs.
export PYTHONPYCACHEPREFIX="$HOME/.cache/python-pycache"

# 3) History settings
HISTSIZE=1000
SAVEHIST=2000
setopt hist_ignore_dups      # no duplicate entries
setopt hist_ignore_space     # no entries starting with space
setopt append_history        # append, don’t overwrite
setopt inc_append_history    # write each command as you go

# 5) (Optional) recursive globstar

# 6) make less nicer
[[ -x /opt/bin/lesspipe ]] && eval "$(SHELL=/system/bin/sh lesspipe)"

# 7) Prompt
if (( EUID == 0 )); then
  PS1='%K{#DD4B39} $ %K{#0087AF}%K{#ffffff} %m %K{#535555}%K{#ffffff} %~ %K{#535555}%k%f '
else
  PS1='%K{#FF0000} $ %K{#800080}%K{#800080} %n@%m %K{#535555}%K{#ffffff} %~ %K{#535555}%k%f '
fi

# 8) Aliases
alias cp="cp -i"
alias df='df -h'
alias free='free -m'
alias more=less

alias ll='ls -alF'
alias la='ls -a'
alias l='ls -CF'
alias ls='ls --color=auto -a'

alias dnfu='sudo -S dnf update -y && sudo -S flatpak update -y && sudo snap refresh'
alias qenv='source ~/.local/venvs/qtile/bin/activate'
alias qcheck='~/.local/venvs/qtile/bin/qtile check'
alias qconf='vim ~/.config/qtile/config.py'
alias qvalid='( source ~/.local/venvs/qtile/bin/activate && qtile check )'
alias qlogs='tail -f ~/.local/share/qtile/qtile.log'
alias qstart='~/.local/venvs/qtile/bin/qtile start'
alias qrefresh='qtile cmd-obj -o . -f reload_config'

alias dc='docker compose'
alias denv='nano ./.env'
alias treex="tree -I 'node_modules|dist|.git|.sonar|.scannerwork' --prune -a -C"
alias ld="lazydocker"
alias flatpak='http_proxy="$http_proxy" https_proxy="$https_proxy" ftp_proxy="$ftp_proxy" all_proxy="$all_proxy" flatpak'

# 9) ex – archive extractor
ex() {
  if [[ -f $1 ]]; then
    case $1 in
      *.tar.bz2)   tar xjf $1 ;;
      *.tar.gz)    tar xzf $1 ;;
      *.bz2)       bunzip2 $1 ;;
      *.rar)       unrar x $1 ;;
      *.gz)        gunzip $1 ;;
      *.tar)       tar xf  $1 ;;
      *.tbz2)      tar xjf $1 ;;
      *.tgz)       tar xzf $1 ;;
      *.zip)       unzip  $1 ;;
      *.Z)         uncompress $1 ;;
      *.7z)        7z x $1 ;;
      *)           echo "'$1' cannot be extracted via ex()" ;;
    esac
  else
    echo "'$1' is not a valid file"
  fi
}

# 10) enable color support for ls/grep if dircolors exists
if [[ -x /opt/bin/dircolors ]]; then
  [[ -r ~/.dircolors ]] && eval "$(dircolors -b ~/.dircolors)" \
                      || eval "$(dircolors -b)"
  alias ls='ls --color=auto -a'
  alias grep='grep --color=auto'
  alias fgrep='fgrep --color=auto'
  alias egrep='egrep --color=auto'
fi

# 11) source additional aliases if present
[[ -f ~/.bash_aliases ]] && source ~/.bash_aliases

# 12) enable bash-style completion (if you really need it)
if [[ -f /opt/etc/bash_completion ]]; then
  source /opt/etc/bash_completion
fi

# bun completions
[ -s "/home/admin/.bun/_bun" ] && source "/home/admin/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

alias kubectl="minikube kubectl --"

[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv zsh)"
if [ /usr/local/bin/kubectl ]; then source <(kubectl completion zsh); fi

# Generated for envman. Do not edit.
[ -s "$HOME/.config/envman/load.sh" ] && source "$HOME/.config/envman/load.sh"

# opencode
export PATH=/home/admin/.opencode/bin:$PATH

# Point the docker CLI at rootless podman's Docker-compatible socket (no daemon).
export DOCKER_HOST="unix:///run/user/1000/podman/podman.sock"

# Build with podman/buildah, not containerized BuildKit: BuildKit can't reach the
# host trust store and fails to verify the internal CA (x509 unknown authority).
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0

# Maschinenlokale Werte (Secrets, interne Hosts/IPs), nicht im Repo.
[ -f ~/.zshrc.local ] && source ~/.zshrc.local
