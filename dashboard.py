import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuração da Página
st.set_page_config(
    page_title="Dashboard de Análise de Logs",
    # page_icon="",
    layout="wide"
)

# Título Principal
st.title(" Dashboard de Análise de Logs do Servidor")
st.markdown("Uma visão interativa dos acessos, performance e visitantes.")

# Função de Carregamento de Dados (Cachada)
@st.cache_data
def load_data():
    try:
        # Carregando o dataset limpo
        df = pd.read_csv('accessLog_Limpo.csv')
        
        # Convertendo coluna de Data para datetime
        # Removendo fuso horário para simplificar visualização, similar à análise original
        df['Data'] = pd.to_datetime(df['Data']).dt.tz_localize(None)
        
        # Extraindo hora e dia da semana dinamicamente
        df['hora'] = df['Data'].dt.hour
        df['dia_semana'] = df['Data'].dt.day_name()
        
        # Traduzindo dias da semana
        dias_traducao = {
            'Monday': 'Segunda-feira', 'Tuesday': 'Terça-feira', 'Wednesday': 'Quarta-feira',
            'Thursday': 'Quinta-feira', 'Friday': 'Sexta-feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
        }
        df['dia_semana_pt'] = df['dia_semana'].map(dias_traducao)
        
        return df
    except FileNotFoundError:
        st.error("Erro: Arquivo 'accessLog_Limpo.csv' não encontrado. Certifique-se de que ele está no mesmo diretório.")
        return pd.DataFrame()

# Carregar Dados
df = load_data()

if not df.empty:
    # --- Sidebar: Filtros ---
    st.sidebar.header("Filtros")
    
    # Filtro de Data
    min_date = df['Data'].min().date()
    max_date = df['Data'].max().date()
    
    # Se houver apenas um dia, mostra esse dia, senão permite intervalo
    if min_date == max_date:
        st.sidebar.info(f"Dados disponíveis para: {min_date}")
        filtered_df = df
    else:
        start_date, end_date = st.sidebar.date_input(
            "Selecione o Intervalo de Datas",
            value=[min_date, max_date],
            min_value=min_date,
            max_value=max_date
        )
        filtered_df = df[(df['Data'].dt.date >= start_date) & (df['Data'].dt.date <= end_date)]

    # Filtro de Status Code
    status_options = sorted(filtered_df['Status'].unique())
    selected_status = st.sidebar.multiselect(
        "Códigos de Status",
        options=status_options,
        default=status_options,
        help="Filtre por código de resposta HTTP (ex: 200, 404, 500)"
    )
    
    # Filtro de Método
    method_options = sorted(filtered_df['Metodo'].unique())
    selected_methods = st.sidebar.multiselect(
        "Métodos HTTP",
        options=method_options,
        default=method_options
    )
    
    # Aplicando filtros secundários
    filtered_df = filtered_df[
        (filtered_df['Status'].isin(selected_status)) &
        (filtered_df['Metodo'].isin(selected_methods))
    ]

    # --- KPIs Principais ---
    col1, col2, col3, col4 = st.columns(4)
    
    total_req = len(filtered_df)
    unique_ips = filtered_df['IP'].nunique()
    if not filtered_df.empty:
        error_req = len(filtered_df[filtered_df['Status'] >= 400])
        error_rate = (error_req / total_req) * 100
        top_url = filtered_df['URL_Limpa'].mode()[0] if not filtered_df['URL_Limpa'].mode().empty else "N/A"
        # Truncar URL longa para exibição
        top_url_display = (top_url[:30] + '..') if len(top_url) > 30 else top_url
    else:
        error_rate = 0
        top_url_display = "N/A"

    col1.metric("Total de Requisições", f"{total_req:,}")
    col2.metric("IPs Únicos", f"{unique_ips:,}")
    col3.metric("Taxa de Erros (4xx/5xx)", f"{error_rate:.2f}%")
    col4.metric("URL Mais Visitada", top_url_display, help=f"Completa: {top_url if 'top_url' in locals() else ''}")

    st.markdown("---")

    # --- Abas de Análise ---
    tab1, tab2, tab3 = st.tabs(["Visão Temporal", " Recursos & Performance", " Visitantes"])

    with tab1:
        st.subheader("Evolução do Tráfego")
        
        # Agrupamento por hora
        req_by_time = filtered_df.groupby(filtered_df['Data'].dt.floor('H')).size().reset_index(name='Requisições')
        
        if not req_by_time.empty:
            fig_time = px.line(
                req_by_time, 
                x='Data', 
                y='Requisições', 
                title='Volume de Requisições por Hora',
                markers=True
            )
            st.plotly_chart(fig_time, use_container_width=True)
        
        # Horários de Pico (Bar Chart)
        st.subheader("Horários de Pico")
        req_by_hour = filtered_df.groupby('hora').size().reset_index(name='Requisições')
        
        fig_peak = px.bar(
            req_by_hour,
            x='hora',
            y='Requisições',
            title='Distribuição de Acessos por Hora do Dia',
            color='Requisições',
            color_continuous_scale='Viridis'
        )
        fig_peak.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=1))
        st.plotly_chart(fig_peak, use_container_width=True)

    with tab2:
        col_rec1, col_rec2 = st.columns(2)
        
        with col_rec1:
            st.subheader("Top 10 URLs Mais Acessadas")
            top_urls = filtered_df['URL_Limpa'].value_counts().head(10).reset_index()
            top_urls.columns = ['URL', 'Acessos']
            
            fig_urls = px.bar(
                top_urls,
                x='Acessos',
                y='URL',
                orientation='h',
                title='Recursos Mais Populares',
                color='Acessos'
            )
            fig_urls.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_urls, use_container_width=True)
            
        with col_rec2:
            st.subheader("Códigos de Status HTTP")
            status_counts = filtered_df['Status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Quantidade']
            
            fig_status = px.pie(
                status_counts,
                names='Status',
                values='Quantidade',
                title='Distribuição de Status Code',
                hole=0.4
            )
            st.plotly_chart(fig_status, use_container_width=True)
            
        st.subheader("Métodos HTTP")
        method_counts = filtered_df['Metodo'].value_counts().reset_index()
        method_counts.columns = ['Método', 'Quantidade']
        fig_method = px.bar(method_counts, x='Método', y='Quantidade', color='Método', title="Uso de Métodos HTTP")
        st.plotly_chart(fig_method, use_container_width=True)

    with tab3:
        col_vis1, col_vis2 = st.columns(2)
        
        with col_vis1:
            st.subheader("Top Navegadores")
            browser_counts = filtered_df['Navegador'].value_counts().head(10).reset_index()
            browser_counts.columns = ['Navegador', 'Uso']
            fig_browser = px.pie(browser_counts, names='Navegador', values='Uso', hole=0.4)
            st.plotly_chart(fig_browser, use_container_width=True)
            
        with col_vis2:
            st.subheader("Sistemas Operacionais")
            os_counts = filtered_df['Sistema_Operacional'].value_counts().head(10).reset_index()
            os_counts.columns = ['Sistema Operacional', 'Uso']
            fig_os = px.bar(os_counts, x='Sistema Operacional', y='Uso', color='Uso')
            st.plotly_chart(fig_os, use_container_width=True)
            
        
        # Mapa de Calor (Se houver latitude e longitude)
        if 'Latitude' in filtered_df.columns and 'Longitude' in filtered_df.columns:
            st.subheader("Origem Geográfica dos Acessos")
            # Remover duplicatas de localização para não plotar milhões de pontos, focar em densidade
            # Ou agregar por localização
            map_data = filtered_df.dropna(subset=['Latitude', 'Longitude'])
            
            if not map_data.empty:
                # Agregando por lat/long para performance
                map_agg = map_data.groupby(['Latitude', 'Longitude']).size().reset_index(name='Acessos')
                
                fig_map = px.scatter_mapbox(
                    map_agg,
                    lat="Latitude",
                    lon="Longitude",
                    size="Acessos",
                    color="Acessos",
                    zoom=0,
                    mapbox_style="open-street-map",
                    title="Mapa de Calor de Acessos"
                )
                fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.info("Dados de geolocalização não disponíveis para visualização no mapa.")
        
        col_loc1, col_loc2 = st.columns(2)
        
        with col_loc1:
            if 'Pais' in filtered_df.columns:
                st.subheader("Top Países")
                country_counts = filtered_df['Pais'].value_counts().head(10).reset_index()
                country_counts.columns = ['País', 'Acessos']
                fig_country = px.bar(country_counts, x='Acessos', y='País', orientation='h', title="Acessos por País")
                fig_country.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_country, use_container_width=True)
                
        with col_loc2:
             # Análise de Dispositivos (Mobile/Tablet/PC/Bot)
            st.subheader("Tipo de Dispositivo")
            device_cols = {'E_Mobile': 'Mobile', 'E_Tablet': 'Tablet', 'E_PC': 'PC', 'E_Bot': 'Bot'}
            device_counts = {}
            
            for col, name in device_cols.items():
                if col in filtered_df.columns:
                    # Contar True values
                    count = filtered_df[col].sum()
                    if count > 0:
                        device_counts[name] = count
            
            if device_counts:
                df_devices = pd.DataFrame(list(device_counts.items()), columns=['Dispositivo', 'Quantidade'])
                fig_devices = px.pie(df_devices, values='Quantidade', names='Dispositivo', title='Distribuição por Dispositivo')
                st.plotly_chart(fig_devices, use_container_width=True)
            else:
                 st.info("Informações de dispositivo não disponíveis.")

        st.subheader("Top IPs (Clientes Mais Ativos)")
        top_ips = filtered_df['IP'].value_counts().head(10).reset_index()
        top_ips.columns = ['IP', 'Requisições']
        st.table(top_ips)

else:
    st.warning("Nenhum dado encontrado para exibir.")

st.markdown("---")
