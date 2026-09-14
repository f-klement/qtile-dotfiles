# ~/.bashrc: executed by bash(1) for non-login shells.

[ -z "$PS1" ] && return

export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"

# Keep __pycache__ out of the stowed (symlinked) config dirs.
export PYTHONPYCACHEPREFIX="$HOME/.cache/python-pycache"

HISTCONTROL=ignoreboth

shopt -s histappend

HISTSIZE=1000
HISTFILESIZE=2000

shopt -s checkwinsize

[ -x /opt/bin/lesspipe ] && eval "$(SHELL=/system/bin/sh lesspipe)"

if [[ ${EUID} == 0 ]] ; then
    PS1='\[\033[48;2;221;75;57;38;2;255;255;255m\] \$ \[\033[48;2;0;135;175;38;2;221;75;57m\]\[\033[48;2;0;135;175;38;2;255;255;255m\] \h \[\033[48;2;83;85;85;38;2;0;135;175m\]\[\033[48;2;83;85;85;38;2;255;255;255m\] \w \[\033[49;38;2;83;85;85m\]\[\033[00m\] '
else
    PS1='\[\033[48;2;105;121;16;38;2;255;255;255m\] \$ \[\033[48;2;0;135;175;38;2;105;121;16m\]\[\033[48;2;0;135;175;38;2;255;255;255m\] \u@\h \[\033[48;2;83;85;85;38;2;0;135;175m\]\[\033[48;2;83;85;85;38;2;255;255;255m\] \w \[\033[49;38;2;83;85;85m\]\[\033[00m\] '
fi
alias cp="cp -i"                          # confirm before overwriting something
alias df='df -h'                          # human-readable sizes
alias free='free -m'                      # show sizes in MB
alias more=less

ex ()
{
  if [ -f $1 ] ; then
    case $1 in
      *.tar.bz2)   tar xjf $1   ;;
      *.tar.gz)    tar xzf $1   ;;
      *.bz2)       bunzip2 $1   ;;
      *.rar)       unrar x $1     ;;
      *.gz)        gunzip $1    ;;
      *.tar)       tar xf $1    ;;
      *.tbz2)      tar xjf $1   ;;
      *.tgz)       tar xzf $1   ;;
      *.zip)       unzip $1     ;;
      *.Z)         uncompress $1;;
      *.7z)        7z x $1      ;;
      *)           echo "'$1' cannot be extracted via ex()" ;;
    esac
  else
    echo "'$1' is not a valid file"
  fi
}

if [ -x /opt/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto -a'

    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

alias ll='ls -alF'
alias la='ls -a'
alias l='ls -CF'
alias ls='ls --color=auto -a'
alias qenv='source ~/.local/venvs/qtile/bin/activate'
alias qcheck='~/.local/venvs/qtile/bin/qtile check'
alias qconf='vim ~/.config/qtile/config.py'
alias qvalid='( source ~/.local/venvs/qtile/bin/activate && qtile check )'
alias qlogs='tail -f ~/.local/share/qtile/qtile.log'
alias qstart='~/.local/venvs/qtile/bin/qtile start'

if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi

if [ -f /opt/etc/bash_completion ] && ! shopt -oq posix; then
    . /opt/etc/bash_completion
fi
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
alias kubectl="minikube kubectl --"

[ -f ~/.fzf.bash ] && source ~/.fzf.bash
. "$HOME/.cargo/env"

# Generated for envman. Do not edit.
[ -s "$HOME/.config/envman/load.sh" ] && source "$HOME/.config/envman/load.sh"

# Maschinenlokale Werte (Secrets, interne Hosts/IPs), nicht im Repo.
[ -f ~/.bashrc.local ] && source ~/.bashrc.local
