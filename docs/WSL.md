# Запуск в WSL 2

## Копия проекта

Рекомендуется хранить проект в Linux FS:

```bash
cd /home/user
cp -a /mnt/c/Users/User/Desktop/liya .
cd liya
```

## Проверка

```bash
./scripts/check-wsl.sh
```

Для Ubuntu может потребоваться:

```bash
sudo apt update
sudo apt install python3.14-venv ffmpeg
```

## Окружение

```bash
./scripts/setup-wsl.sh
```

Если `python3-venv` не установлен, выполните указанную выше команду с `sudo`, затем повторите setup.

## llama.cpp

Скачайте или соберите `llama.cpp`, затем положите GGUF-модель в `models/`:

```bash
./scripts/run-llama.sh /home/user/liya/models/model.gguf
```

MLX недоступен в WSL. Для WSL используйте llama.cpp/GGUF, а MLX оставьте macOS-профилем.

## Проверка приложения

```bash
source .venv/bin/activate
liya doctor
liya chat
```