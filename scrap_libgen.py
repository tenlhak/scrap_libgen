import os
import requests
from bs4 import BeautifulSoup
import pandas as pd


output_dir = 'downloaded_books_libgen'  #name your output dir 
if not os.path.exists(output_dir):
    os.makedirs(output_dir)


file_path = 'YorBookList.xlsx'  #the list of books names stored in excel file
df = pd.read_excel(file_path)


book_titles = df['Title'].tolist()

# Function to download the book file
def download_book(url, output_path):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded: {output_path}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

#function to scrape book details from Libgen based on the search term
def search_libgen(book_title):
    search_url = f"http://libgen.rs/search.php?req={book_title.replace(' ', '+')}&open=0&res=25&view=simple&phrase=1&column=def"

    #send request
    response = requests.get(search_url)

    #check if the request was successful
    if response.status_code != 200:
        print(f"Request failed with status code {response.status_code} for book: {book_title}")
        return
    
    #parse the HTML content
    soup = BeautifulSoup(response.content, 'html.parser')


    #now at the time of wrting this code follwing was the HTML syntax of libgen, but they keep on changing so you mgiht wanna check!!
    #find all rows in the table that contain book data (skip the header row)
    book_rows = soup.find_all('tr', valign="top")

    for row in book_rows:
        columns = row.find_all('td')

        #extract author names (second <td>)
        authors = [a.text for a in columns[1].find_all('a')]

        #extract book title (third <td>)
        title_tag = columns[2].find('a')
        title = title_tag.text if title_tag else 'No Title'

        #extract download links (from the last few <td> elements)
        download_links = []
        for col in columns[-3:]:  #iterate through the last 3 columns
            links = col.find_all('a')  #find all links in this column
            download_links.extend([a['href'] for a in links])  #add the href attribute of each link

        if download_links:
            #use the first download link (usually the most reliable one)
            download_url = download_links[0]
            
            #create a safe filename for the book
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}.pdf"  #you might want to change the file extension based on the actual format (e.g., pdf, epub, etc.)
            output_path = os.path.join(output_dir, filename)
            
            #download the book
            print(f"Downloading {title} by {', '.join(authors)}")
            download_book(download_url, output_path)

#loop through each book title from the Excel file and search Libgen
for book_title in book_titles:
    print(f"Searching for: {book_title}")
    search_libgen(book_title)
    print('-' * 40)  #separator between each search result
