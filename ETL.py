# %% [markdown]
# # **Construção de um Pipeline de Dados Simples para Análise de Logs de Servidor Web**

# %% [markdown]
# ## **Contexto**
# Os logs de servidor da Web contêm informações sobre qualquer evento que foi registrado/registrado. Isso contém muitos insights sobre visitantes do site, comportamento, rastreadores que acessam o site, insights de negócios, problemas de segurança e muito mais.
# 
# Este é um conjunto de dados para tentar obter insights desse arquivo.

# %%
'''
OBs: Um pipeline de dados é uma sequência de etapas interconectadas que permitem a coleta, armazenamento, transformação, análise e visualização de dados
'''
import locale
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import requests
import re
from urllib.parse import urlparse, quote, unquote
from user_agents import parse
import sqlite3

# %%
pd.set_option('display.max_columns', None)

# %% [markdown]
# ## **1. Exctração**

# %%
def extract(file, tamanho):
    with open (file,'r') as archive:
        return archive.read(tamanho) 

# %%
tamanho =8500000#
arquivo = extract('access.log', tamanho)
print(arquivo) # printando os arquivos
print(f'\n\nA quantidade de caracteres que forma lidos -> {float(len(arquivo))}')

# %% [markdown]
# # **2. o que tem neste arquivo log?**
# - ***IP***: 54.36.149.41
# 
# - ***Data***: 22/Jan/2019:03:56:14 +0330
# - ***Método***: GET
# - ***URL***: /filter/27|13%20%D9%85%DA%AF%D8%A7%D9%BE%DB%8C%DA%A9%D8%B3%D9%84
# - ***Protocolo***: HTTP/1.1
# - ***Status***: 200
# - ***Tamanho***: 30577
# - ***User***-Agent: Mozilla/5.0 (compatible; AhrefsBot/6.1; +http://ahrefs.com/robot/)

# %% [markdown]
# # **3. Transformação**

# %%
def convert_pd(data_extract): # Mandando os dados para ser tranformados e organizados no pandas

    logpadrao = r'''(\d+\.\d+\d+\.\d+\.\d+) - - \[([^\]]+)\] "(\w+) ([^"]+) ([^"]+)" (\d+) (\d+) "-" "([^"]+)'''
    resultado = re.finditer(logpadrao, data_extract)
    data_convert = [
        {
                'Ip': res.group(1), # pegando o endereco IP
                'Date': res.group(2), # pegando a Data
                'Methode':res.group(3), # pegando o Metodo
                'URL': res.group(4), # pegando a URL
                'Protocol': res.group(5), # pegando o protrocolo
                'Status': int(res.group(6)), # Pegando status
                'Size': int(res.group(7)),# Tamanho
                'User-Agent': res.group(8) # Angente usuario ex.: Bot ou robos
        }  
        for res in resultado
    ]   
    return pd.DataFrame(data_convert)

# %%
df = convert_pd(arquivo)
df.info()

# %% [markdown]
# #  **2. Padronização de formatos**
# ## ***2.1. Formatando o tempo***

# %%
df['Date'] = pd.to_datetime(df['Date'], format="%d/%b/%Y:%H:%M:%S %z").dt.tz_localize(None)# formatação do tempo
df.Date.astype(str)
df.head() # 

# %%
df.info() # vendo se o tempo foi formatado

# %% [markdown]
# # **3. Remoção de duplicidades e erros**

# %%
df = df.drop_duplicates() # apagando os dados duplicados

# %%
df.isna().sum() # verificando se há dados faltantes

# %% [markdown]
# ## **4. Padronizando os métodos**

# %%
# 2 - Padronização de métodos HTTP: Deixar todos os métodos (GET, POST, etc.) em maiúsculas.
df.Methode.str.upper().head(2) # get GET gET

# %% [markdown]
# # **5. Fazer a limpeza da URL**

# %% [markdown]
# * Decodificar caracteres especiais.
# * Remover parâmetros irrelevantes (utm, sessionid, etc.).
# * Remover barras finais redundantes.
# * Padronizar domínio e esquema para minúsculas.

# %%
def limparURL(url: str) -> str:
    # validação ----------
    if not isinstance(url, str) or not url.strip():
        return ''

    # ---------- decode ----------
    decoded = unquote(url.strip())

    # ---------- parse ----------
    parsed = urlparse(decoded)

    path = parsed.path or ''

    # ---------- normalizações estruturais ----------
    path = re.sub(r'/+', '/', path)           # múltiplas barras → 1
    path = path.rstrip('/')                   # remove trailing slash
    path = path.replace('|', '-')             # separador consistente
    path = re.sub(r'\s+', '-', path)          # espaços → hífen
    path = re.sub(r'-+', '-', path)           # colapsa hífens

    # remove caracteres inválidos mas mantém unicode válido
    path = re.sub(r'[^\w\-/\u0080-\uFFFF]', '', path)

    path = path.strip('-').lower()

    #  canonical encoding 
    path = quote(path, safe="/-")

    return path


# aplicar dataframe
df["URL"] = df["URL"].apply(limparURL)

df['URL'].head(20)

# %%
url = df.URL
url[url.isnull() == True] = '/'
df.URL = url

# %%
df =  df[['Ip', 'Date', 'Methode', 'URL', 'Protocol', 'Status', 'Size','User-Agent']]
df.head(3)

# %% [markdown]
# # **6 - Normalizar os User-Agent**
# **User-Agent:** São as infromacões que o cliente (navegador ou app) envia num servidor 
# quando faz a requisicao.
# O que importa no user-agent:
# """
# 1. **Cliente/Navegador** {
#     * Chrome
#     * Firefox
#     * Safari
#     * Edge
#     * Bots (Googlebot, Bingbot, etc.) - é um cliente
#     * Apps (curl, python-requests…) - é um cliente
#     
# }
# 
# 2. **Versao do navegador** {
#     * Chrome 122
#     * Firefox 115
#      
# }
# 
# 3. **Sistema operativo** {
#     * Windows 10/11
#     * Android 13
#     * iOS 17
#     * Linux
#      
# }
# 
# 4. **Tipo de dispositivo** {
#     * Desktop
#     * Mobile
#     * Tablet
#     * Smart TV
#     * Bot / Crawler
# }
# 5. **Motor do browser** {
#     * Blink
#     * WebKit
#     * Gecko
# 
# }
# 

# %%
# Formatação dos user-agentes
def user_agents(ua_string):
    ua = parse(ua_string)
    return pd.Series({
        "browser": ua.browser.family, # o tipo de navegador
        "browser_version": ua.browser.version_string, # versao do navegador
        "os": ua.os.family, # verificando o tipo de sistema operacional
        "os_version": ua.os.version_string, # a versao do sistema operacional
        "device": ua.device.family, # O despositivo
        "is_mobile": ua.is_mobile, # é despositivo movel
        "is_tablet": ua.is_tablet,
        "is_pc": ua.is_pc,
        "is_bot": ua.is_bot
    })

df_parced = df['User-Agent'].apply(user_agents)
df = pd.concat([df,df_parced], axis = 1)
df.drop(columns = 'User-Agent', inplace = True)
df.head()

# %% [markdown]
# # **7 - Enriquecer os dados** 
# ## **7.1 Geolocalizar endereços IP**

# %%
# Para que nao haja problemas criei uma copia do dataset
df_original = df.copy()

# %%
# Caso há
ips_unicos = (
    df_original["Ip"]
    .dropna()
    .astype(str)
    .unique()
)
ips_unicos.size

# %%


# %%
ips = ips_unicos
dados_ips = ips.tolist() # conrtendo para lista
# dados_ips

# %%
format_ip = []
for IP in dados_ips:
    try:
        r = requests.get(f'http://ip-api.com/json/{IP}?fields=status,message,continent,continentCode,country,countryCode,region,regionName,city,district,zip,lat,lon,timezone,isp,org,as,asname,reverse,mobile,proxy,hosting,query',
            timeout=15
        )

        if r.status_code != 200:
            print("Erro HTTP:", r.status_code, r.text)
            continue

        if "application/json" not in r.headers.get("Content-Type",""):
            print("Resposta não JSON:", r.text)
            continue
        elif r.status_code == 200:
            print(r.json())
        format_ip.append(r.json())

    except requests.RequestException as e:
        print("Erro de requisição:", e)

# %%
len(format_ip)

# %%
ip_geo = pd.DataFrame(format_ip)
# ip_geo = pd.read_csv('Ips2.csv')
ip_geo.columns

# %%
ip_geo.to_csv('Ips.csv')

# %%
ip_geo.isnull().sum()

# %%
df_final = df_original.merge(ip_geo, left_on='Ip', right_on='query', how = 'left')


# %%
df_final.head()

# %%
df_final.isnull().sum()

# %%
df_final.columns

# %%
# Organizando as colunas e pegando tabelas essencial para a análise
df_final = df_final[['Ip', 'Date', 'Methode', 'URL', 'Protocol', 'Status', 'is_mobile',
       'is_tablet', 'is_pc', 'is_bot', 'browser', 'os','continent','country', 'countryCode', 'regionName', 'city', 'lat', 'lon',
       'isp', 'org', 'as', 'proxy',
       'hosting', 'query']]

# %%
df_final.columns

# %%
df_final.isnull().sum()

# %%
df_final.org = df_final.org.fillna('Not Found')

# %%
df_final.dropna(subset = [
       'country', 'lat','lon', 'city', 'as', 'countryCode',
       'regionName', 'isp'],inplace = True)

# %%
df_final.isnull().sum()

# %%
df_final.columns

# %%
df_final.proxy = df_final.proxy.astype(bool)
df_final.hosting = df_final.hosting.astype(bool)


# %%
df_final.info()

# %% [markdown]
# # **Load**
#  - Carregar os dados num DataWareause: SQL & CSV

# %%
# VALIDATE
# assert df["valor"].min() >= 0
assert df["Date"].notnull().all()

# %%
df_final

# %%
df_final.info()

# %%
df_final = df_final.rename(columns={
    'Ip'                : 'Ip',
    'Date'              : 'Data',
    'Methode'           : 'Metodo',
    'URL'               : 'URL',
    'Protocol'          : 'Protocolo',
    'status_code'       : 'Codigo_Status',
    'is_mobile'         : 'E_Mobile',
    'is_tablet'         : 'E_Tablet',
    'is_pc'             : 'E_Pc',
    'is_bot'            : 'E_Bot',
    'browser'           : 'Navegador',
    'os'                : 'Sistema_Operacional',
    'continent'         : 'Continente',
    'country'           : 'Pais',
    'countryCode'       : 'Codigo_Pais',
    'regionName'        : 'Regiao',
    'city'              : 'Cidade',
    'lat'               : 'Latitude',
    'lon'               : 'Longitude',
    'isp'               : 'Isp',
    'org'               : 'Organizacao',
    'as'                : 'As',
    'proxy'             : 'Proxy',
    'hosting'           : 'Hospedagem',
    'query'             : 'Consulta'
})

# %%
df_final.to_pickle('log_dw.pkl') # salvando em pkl com todas as formatações bem definidas.

# %%
conn = sqlite3.connect('logServidores_web.db')
df_final.to_sql('log', conn, if_exists = 'replace', index = False)


