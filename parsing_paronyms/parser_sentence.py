import pathlib
from typing import List

from selenium import webdriver
from selenium.webdriver.common.by import By
from tqdm import tqdm


driver = webdriver.Chrome()
# driver.get("https://rus-ege.sdamgia.ru/test?id=50168830&nt=True&pub=False&print=true&svg=0&num=true&ans=true&tt=&td=")
driver.get("https://rus-ege.sdamgia.ru/test?id=50214784&nt=True&pub=False&print=true&svg=0&num=true&ans=true&tt=&td=")

all_divs = driver.find_elements(By.TAG_NAME, 'div')

relative_pairs: List[tuple[List, str]] = []
for div in tqdm(all_divs):
    style = div.get_attribute('class')
    if style and 'prob_maindiv' in style:
        div_little = div.find_element(By.CLASS_NAME, 'nobreak')
        p = list(filter(lambda x: x.text, div_little.find_elements(By.TAG_NAME, 'p')))[2:]
        ans = div.find_element(By.CLASS_NAME, 'answer').text
        relative_pairs.append((p, ans))

print('Start writes in file')
with pathlib.Path('../words/sentence.txt').open(mode='w', encoding='utf-8') as file:
    for options, ans in tqdm(relative_pairs):
        for p in options:
            print(p.text.replace('­', '').replace('  ', ' ').replace(' ', ' '), file=file)
        print(ans, file=file)

driver.quit()