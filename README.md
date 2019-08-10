serial-notifier
===============

**[ENG]**

serial-notifier is an application for tracking of release new series.

Application`s features:
* marking of watched series;
* receiving of notifications about released new series;
* support custom plugins for notifying.

Application supports receiving of information from 2 web sites:

* filin.tv
* filmix.co

It has an opportunity of working via proxy server. You can manage it by editing 
of setting.conf.

## Install and launch

Requirements:

- python >= 3.6
- poetry

To install libraries, execute the below command:

```bash
poetry install --no-dev
```

If you want to install the dependencies you need to develop, execute the 
below command:

```bash
poetry install
```

To start the program you need to launch the script `serial_notifier.py`.

## Adding new series to tracking

To add a new series to the track list, you should declare it in the
`sites.conf` file. It is located at the root of the program folder (if it 
is not exist, it will be created automatically with the first run).

_Example sites.conf_

```ini
[filin.tv]
urls = Под куполом;http://www.filin.tv/fantastika/2025-pod-kupolom-under-the-dome-1-sezon-onlajn.html
    Штамм;http://www.filin.tv/fantastika/2886-shtamm-the-strain-1-sezon-onlayn.html
encoding = cp1251

[filmix.me]
urls = Игра престолов;http://filmix.co/serialy/112983-igra-prestolov-2016.html
    Бойтесь ходячих мертвецов;http://filmix.co/dramy/101118-boytes-hodyachih-mertvecov-fear-the-walking-dead-serial-2015.html
    Флэш;http://filmix.co/fantastika/90379-flesh-the-flash-serial-2014.html
encoding =
```

**[RU]**

serial-notifier - это приложение для отслеживания выхода новых серий (сезонов) 
любимых сериалов.
Оно позволяет Вам:

* отмечать какие серии Вы посмотрели;
* в автоматическом режиме получать уведомления о выходе новых серий (сезонов);
* добавлять собственные плагины, которые будут присылать уведомления в 
необходимое для вас место.

Поддерживается получение информации о новых сериях с 2 сайтов:

* filin.tv
* filmix.co

Приложение умеет обходить блокировоки при помощи прокси серверов (настроить 
это можно в setting.conf). 
По этому если сайт по которому происходило отслеживание новых серий 
заблокируют, приложение не перестанет работать.

## Установка и запуск

Зависимости:

- python >= 3.6
- poetry

После того как основные зависимости установлены, необходимо выполнить установку
бибилиотек необходимых для работы приложения (команду описанную ниже, 
необходимо выполнять находясь в корне проекта):

```bash
poetry install --no-dev
```

Если нужно уставить зависимости необходимые для разработки, то выполните 
команду:

```bash
poetry install
```

Для того, что запустить программу, необходимо исполнить скрипт
`serial_notifier.py`.

## Добавление новых сериалов для отслеживания

Для добавления нового сериала в список отслеживаемых, необходимо объявить его в
файле `sites.conf`. Он располагается в корне папки с программой (если его нет,
то при первом запуске он будет создан автоматически).

_Пример sites.conf_

```ini
[filin.tv]
urls = Под куполом;http://www.filin.tv/fantastika/2025-pod-kupolom-under-the-dome-1-sezon-onlajn.html
    Штамм;http://www.filin.tv/fantastika/2886-shtamm-the-strain-1-sezon-onlayn.html
encoding = cp1251

[filmix.me]
urls = Игра престолов;http://filmix.co/serialy/112983-igra-prestolov-2016.html
    Бойтесь ходячих мертвецов;http://filmix.co/dramy/101118-boytes-hodyachih-mertvecov-fear-the-walking-dead-serial-2015.html
    Флэш;http://filmix.co/fantastika/90379-flesh-the-flash-serial-2014.html
encoding =
```