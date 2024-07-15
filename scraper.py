import re
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from base64 import b64decode
import requests
import pandas as pd
from itertools import chain
import argparse

def main(location):
    # 配置和初始化 Selenium WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    # 第一层：获取所有 chart 和 collections 的 URL
    url = location
    driver.get(url)

    # 等待页面加载并获取链接
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'chart-link')))
    chart_links = driver.find_elements(By.CLASS_NAME, 'chart-link')
    more_links = driver.find_elements(By.CLASS_NAME, 'btn--more')

    # 提取 href 属性
    unique_urls = list(set(link.get_attribute('href') for link in chain(chart_links, more_links) if link.get_attribute('href')))
    collection_urls = [url for url in unique_urls if 'collections' in url]
    non_collection_urls = [url for url in unique_urls if 'collections' not in url]

    driver.quit()

    # 过滤掉重复的 collections 号码
    unique_collections = set()
    filtered_collection_urls = []

    for url in collection_urls:
        collection_part = "/".join(url.split('/')[:5])
        if collection_part not in unique_collections:
            unique_collections.add(collection_part)
            filtered_collection_urls.append(url)

    # 第二层：爬每个 collections 里面所有含 collections 的 URL
    results = []

    for url in filtered_collection_urls:
        try:
            api_response = requests.post(
                "https://api.zyte.com/v1/extract",
                auth=("1efb03ddb3a749c68d7528ee0880d56a", ""),  # Replace with your actual API credentials
                json={"url": url, "httpResponseBody": True},
            )
            response_json = api_response.json()

            if api_response.status_code == 200 and "httpResponseBody" in response_json:
                http_response_body = b64decode(response_json["httpResponseBody"])
                results.append(http_response_body)
            else:
                print(f"Failed to fetch data from {url}")
        except Exception as e:
            print(f"Error processing URL {url}: {e}")

    # 提取所有含 collections 的 URL
    all_filtered_urls = []

    for result in results:
        soup = BeautifulSoup(result.decode('utf-8'), 'html.parser')

        # 提取 <a> 标签中的 URL
        links = soup.find_all('a', href=True)
        pattern_a = re.compile(r'/collections/\d+')
        for link in links:
            href = link['href']
            if pattern_a.search(href):
                full_url = href if href.startswith('http') else 'https://www.macromicro.me' + href
                all_filtered_urls.append(full_url)

        # 提取 <script> 标签中的 URL
        script_tags = soup.find_all('script')
        pattern_script = re.compile(r'https?://www\.macromicro\.me/collections/\d+[^\s",]*')
        for script in script_tags:
            script_content = script.string
            if script_content:
                matches = pattern_script.findall(script_content)
                for match in matches:
                    all_filtered_urls.append(match)

    all_filtered_urls = list(set(all_filtered_urls))

    # 使用 API 爬取每个 URL 并解析 HTML，提取 title 和 content
    data = []

    for url in chain(all_filtered_urls, non_collection_urls):
        try:
            api_response = requests.post(
                "https://api.zyte.com/v1/extract",
                auth=("1efb03ddb3a749c68d7528ee0880d56a", ""),  # Replace with your actual API credentials
                json={"url": url, "httpResponseBody": True},
            )
            response_json = api_response.json()

            if api_response.status_code == 200 and "httpResponseBody" in response_json:
                http_response_body = b64decode(response_json["httpResponseBody"])
                soup = BeautifulSoup(http_response_body.decode('utf-8'), 'html.parser')
                title_tag = soup.find('meta', property="og:title")
                description_tag = soup.find('meta', property="og:description")
                title = title_tag.get('content') if title_tag else "Title not found"
                description = description_tag.get('content') if description_tag else "Meta description not found"
                data.append([title, description, url])
            else:
                print(f"Failed to fetch data from {url}")
        except Exception as e:
            print(f"Error retrieving URL {url}: {e}")
        # Add a slight delay to avoid being blocked by the server
        time.sleep(1)

    df = pd.DataFrame(data, columns=['Title', 'Description', 'URL'])
    df.to_csv('country.new.csv', index=False, encoding='utf-8')
    print("CSV 文件已成功生成。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="爬取指定 URL 并生成 CSV 文件")
    parser.add_argument("location", help="要爬取的 URL")
    args = parser.parse_args()
    main(args.location)
