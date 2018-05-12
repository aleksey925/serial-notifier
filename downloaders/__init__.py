from .async_downloader import AsyncDownloader
from .thread_downloader import ThreadDownloader
# from .go_downloader import GoDownloader

downloader = {
    'async_downloader': AsyncDownloader,
    'thread_downloader': ThreadDownloader,
    # 'go_downloader': GoDownloader,
}
