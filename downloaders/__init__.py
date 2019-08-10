from .async_downloader import AsyncDownloader
from .thread_downloader import ThreadDownloader

downloader = {
    'async_downloader': AsyncDownloader,
    'thread_downloader': ThreadDownloader,
}
