import os

from icrawler.builtin import BingImageCrawler


# Anos que faltam para a sua carga
anos = [
    1930, 1934, 1938, 1950, 1954, 1958, 1962, 1966, 1970,
    1974, 1978, 1982, 1986, 1990, 1994, 1998, 2002, 2006, 2010,
]

for ano in anos:
    # Cria uma pasta para cada ano
    pasta_destino = f"fotos_campeoes/copa_{ano}"
    os.makedirs(pasta_destino, exist_ok=True)

    # Inicia o crawler apontando para o diretório criado
    crawler = BingImageCrawler(storage={"root_dir": pasta_destino})

    # Termos em inglês trazem fotos de arquivos oficiais.
    # "captain" ajuda a focar no momento de levantar a taça.
    query = f"FIFA World Cup {ano} captain lifting trophy"

    print(f"Baixando imagens para a Copa de {ano}...")

    # max_num=5 baixa as cinco primeiras ocorrências.
    crawler.crawl(keyword=query, max_num=5)

print("Scraping finalizado!")
