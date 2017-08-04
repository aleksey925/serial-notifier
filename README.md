**Описание**

serial-notifier - это приложение для отслеживания выхода новых серий или
сезонов любимых сериалов.

Поддерживается получение информации о новых сериях с 2 сайтов:

* filin.tv
* filmix.me

С помощью приложения Вы сможете:

* отмечать какие серии и сериалы Вы посмотрели;
* в автоматическом режиме получать уведомления о выходе новых 
серий и сезонов;
* добавить свои плагины, которые будут присылать уведомления в необходимое
для вас место.

**Установка и запуск**

Для запуска программы необходимо установить python >= 3.6 и зависимости.

P.S При установке на windows необходимо производить установку в режиме 
"Customize installation" и выбрать пункты: `Add Python to PATH` и 
`Install for all users`

Установка зависимостей выполняется командой `pip3 install -r requirements.txt`

После установки python и зависимостей программу папку с программой можно 
разместить в любом удобном месте.

Запустить ее можно кликнув 2 раза по файлу `serial_notifier.py` или запустив 
его из консоли `python3 <path-to-serial_notifier.py>`.

**Добавление сериалов для отслеживания**

Чтобы программа начала отслеживать сериал, его нужно добавить в файл 
sites.conf, который находится в корне папки с программой.

_Пример содержимого sites.conf_

    [filin.tv]
    
    urls = Под куполом;http://www.filin.tv/fantastika/2025-pod-kupolom-under-the-dome-1-sezon-onlajn.html
        Штамм;http://www.filin.tv/fantastika/2886-shtamm-the-strain-1-sezon-onlayn.html
    
    [filmix.me]
    urls = Игра престолов;http://filmix.me//serialy/112983-igra-prestolov-2016.html
        Бойтесь ходячих мертвецов;http://filmix.me//dramy/101118-boytes-hodyachih-mertvecov-fear-the-walking-dead-serial-2015.html
        Флэш;http://filmix.me//fantastika/90379-flesh-the-flash-serial-2014.html