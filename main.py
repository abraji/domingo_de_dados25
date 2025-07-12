# -*- coding: utf-8
# Reinaldo Chaves (reichaves@gmail.com)

import os
# FORÇA O USO DA IMPLEMENTAÇÃO PYTHON DO PROTOBUF PARA EVITAR CONFLITOS
# Isso é necessário porque algumas bibliotecas (como TensorFlow) podem usar implementações
# diferentes do Protocol Buffers, causando conflitos. Forçar a implementação Python
# garante compatibilidade entre todas as bibliotecas
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import time  # Para adicionar delays entre requisições e evitar rate limiting
import pandas as pd  # Para manipulação de dados tabulares e criação de DataFrames
import geopandas as gpd  # Extensão do pandas para dados geoespaciais (shapefiles)
from dotenv import load_dotenv  # Para carregar variáveis de ambiente do arquivo .env
from tqdm import tqdm  # Para criar barras de progresso visuais durante processamento
import logging  # Para registrar logs estruturados do sistema
from datetime import datetime  # Para trabalhar com datas e timestamps
import random  # Para gerar delays aleatórios entre requisições

# === IMPORTAÇÕES DO LANGCHAIN ===
# LangChain é um framework para construir aplicações com LLMs (Large Language Models)

# Vectorstore para armazenar e buscar embeddings de documentos
from langchain_community.vectorstores import Chroma

# Ferramentas de busca na web
from langchain_google_community import GoogleSearchAPIWrapper  # Busca via Google Custom Search
from langchain_community.tools import DuckDuckGoSearchResults  # Busca via DuckDuckGo (fallback)

# Integração com Google Gemini (modelo de IA)
from langchain_google_genai import ChatGoogleGenerativeAI  # Modelo de chat do Gemini
from langchain_google_genai import GoogleGenerativeAIEmbeddings  # Modelo de embeddings

# Utilitários para processamento de texto
from langchain.text_splitter import RecursiveCharacterTextSplitter  # Divide textos longos em chunks
from langchain.chains import RetrievalQA  # Chain para Question-Answering com recuperação
from langchain.prompts import PromptTemplate  # Template para prompts estruturados
from langchain.schema import Document  # Estrutura de dados para documentos

# Carrega as variáveis de ambiente do arquivo .env
# Isso inclui API keys do Google, credenciais, etc.
load_dotenv()

# === CONFIGURAÇÃO DO SISTEMA DE LOGGING ===
# Define formato e nível de logging para toda a aplicação
# INFO: mostra mensagens informativas gerais
# Format: timestamp - nível - mensagem
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Cria logger específico para este módulo

# === CONFIGURAÇÕES GLOBAIS DO SISTEMA ===
# Caminhos e nomes de arquivos utilizados em todo o script

# Caminho para o shapefile com dados do SIGMINE (Sistema de Informações Geográficas da Mineração)
SHAPEFILE_PATH = "data/BRASIL/BRASIL.shp"
'''
Fonte dos dados:
https://dados.gov.br/dados/conjuntos-dados/sistema-de-informacoes-geograficas-da-mineracao-sigmine
Arquivo de Metadados
Processos minerários ativos - Brasil
'''

# Diretório onde serão salvos os resultados
OUTPUT_DIR = "output"

# Nome do arquivo do relatório final em Markdown
REPORT_FILENAME = os.path.join(OUTPUT_DIR, "relatorio_sigmine_contexto.md")

# === NOMES DAS COLUNAS DO SHAPEFILE ===
# Define os nomes das colunas que serão usadas do shapefile
# Isso facilita manutenção caso os nomes mudem
COL_PROCESSO = "PROCESSO"  # Número do processo minerário (ex: 803237/2022)
COL_TITULAR = "NOME"       # Nome da empresa titular do processo
COL_UF = "UF"             # Unidade Federativa (estado)

# Variável global para rastrear qual motor de busca foi efetivamente utilizado
# Será preenchida em runtime com "Google Search API" ou "DuckDuckGo Search"
SEARCH_ENGINE_USED = None

def setup_search_tool():
    """
    Configura a ferramenta de busca na web, priorizando Google Search API.
    
    Esta função tenta primeiro usar o Google Search (mais preciso e estruturado),
    mas se falhar ou não estiver configurado, usa DuckDuckGo como fallback.
    
    Returns:
        search_tool: Instância de GoogleSearchAPIWrapper ou DuckDuckGoSearchResults
    
    A escolha é importante porque:
    - Google Search retorna resultados estruturados (título, link, snippet)
    - DuckDuckGo retorna texto não estruturado que precisa ser parseado
    """
    global SEARCH_ENGINE_USED  # Permite modificar a variável global
    
    # Tenta buscar as credenciais do Google no arquivo .env
    google_api_key = os.getenv("GOOGLE_API_KEY")
    google_cse_id = os.getenv("GOOGLE_CSE_ID")  # Custom Search Engine ID

    # Se ambas as credenciais existem, tenta configurar Google Search
    if google_api_key and google_cse_id:
        try:
            # Cria instância da ferramenta Google Search
            search_tool = GoogleSearchAPIWrapper()
            
            # Testa se a ferramenta funciona fazendo uma busca simples
            test_results = search_tool.run("test query")
            
            # Se retornou resultados, a configuração está correta
            if test_results:
                print("✅ Usando Google Search como ferramenta de busca.")
                SEARCH_ENGINE_USED = "Google Search API"
                return search_tool
                
        except Exception as e:
            # Se houver erro, registra mas continua para o fallback
            logger.warning(f"Google Search API configurada mas falhou: {e}")
    
    # Fallback: usa DuckDuckGo que não precisa de API key
    print("⚠️ Usando DuckDuckGoSearchResults como ferramenta de busca.")
    SEARCH_ENGINE_USED = "DuckDuckGo Search"
    return DuckDuckGoSearchResults()

def extract_urls_from_duckduckgo_text(text):
    """
    Extrai URLs de texto não estruturado retornado pelo DuckDuckGo.
    
    O DuckDuckGo retorna resultados como texto plano, então precisamos
    usar regex para encontrar e extrair as URLs.
    
    Args:
        text (str): Texto bruto retornado pelo DuckDuckGo
        
    Returns:
        list: Lista de URLs únicas encontradas no texto
        
    Exemplo:
        Input: "Resultado sobre mineração... https://exemplo.com/noticia..."
        Output: ["https://exemplo.com/noticia"]
    """
    import re
    
    # Padrão regex para capturar URLs HTTP/HTTPS
    # Captura: protocolo://dominio/caminho
    # Exclui caracteres que normalmente delimitam URLs em texto
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+(?:\.[^\s<>"{}|\\^`\[\]]+)*'
    
    # Encontra todas as URLs que correspondem ao padrão
    urls = re.findall(url_pattern, text)
    
    # Remove duplicatas mantendo a ordem original
    seen = set()  # Conjunto para rastrear URLs já vistas
    unique_urls = []
    
    for url in urls:
        # Ignora URLs que terminam com '.' (comum em fins de frase)
        if url not in seen and not url.endswith('.'):
            seen.add(url)
            unique_urls.append(url)
            
    return unique_urls

def enhanced_search(titular: str, processo: str, uf: str, search_tool):
    """
    Realiza busca aprimorada na web com múltiplas estratégias e Google Dorks.
    
    Esta é uma das funções mais importantes do sistema. Ela implementa
    três estratégias de busca para maximizar as chances de encontrar
    informações relevantes sobre impactos socioambientais.
    
    Args:
        titular (str): Nome da empresa titular do processo
        processo (str): Número do processo (ex: "803237/2022")
        uf (str): Estado (sigla)
        search_tool: Ferramenta de busca configurada
        
    Returns:
        list: Lista de dicionários com resultados de busca estruturados
        
    Estratégias implementadas:
    1. Buscas básicas: termos gerais sobre a empresa
    2. Buscas de impacto: termos específicos sobre conflitos
    3. Buscas direcionadas: usando Google Dorks em sites especializados
    """
    all_results = []  # Lista para acumular todos os resultados
    
    # Remove a barra do número do processo para algumas buscas
    # Ex: "803237/2022" -> "8032372022"
    processo_clean = processo.replace('/', '')
    
    # Lista de sites especializados em questões socioambientais e mineração
    # Estes sites são priorizados porque tendem a ter informações mais confiáveis
    sites_relevantes = [
        "terrasindigenas.org.br",    # Monitoramento de terras indígenas
        "mpf.mp.br",                 # Ministério Público Federal
        "ibama.gov.br",              # Instituto Brasileiro do Meio Ambiente
        "funai.gov.br",              # Fundação Nacional do Índio
        "socioambiental.org",        # Instituto Socioambiental
        "cimi.org.br",               # Conselho Indigenista Missionário
        "imazon.org.br",             # Instituto do Homem e Meio Ambiente da Amazônia
        "inesc.org.br",              # Instituto de Estudos Socioeconômicos
        "apublica.org",              # Agência de jornalismo investigativo
        "reporterbrasil.org.br"      # ONG de jornalismo socioambiental
    ]
    
    # === ESTRATÉGIA 1: BUSCAS BÁSICAS ===
    # Termos mais gerais para capturar informações gerais sobre a empresa/processo
    basic_searches = [
        f'"{titular}" {uf}',           # Busca exata da empresa + estado
        f'"{titular}" mineração',      # Empresa + contexto de mineração
        f'processo {processo}',        # Busca direta pelo número do processo
        f'ANM {processo}',            # ANM = Agência Nacional de Mineração
        f'SIGMINE {processo_clean}',  # SIGMINE + processo sem barra
    ]
    
    # === ESTRATÉGIA 2: BUSCAS COM TERMOS DE IMPACTO ===
    # Termos específicos para encontrar potenciais conflitos e impactos
    impact_searches = [
        f'"{titular}" terra indígena',         # Conflitos com TIs
        f'"{titular}" comunidade tradicional', # Impactos em comunidades
        f'"{titular}" impacto ambiental',     # Estudos de impacto
        f'"{titular}" conflito socioambiental', # Conflitos gerais
        f'"{titular}" ação civil pública',     # Ações judiciais
        f'processo {processo} impacto',       # Impactos do processo específico
        f'processo {processo} terra indígena', # Processo em TIs
    ]
    
    # === ESTRATÉGIA 3: BUSCAS COM GOOGLE DORKS ===
    # Usa operador "site:" para buscar diretamente em sites especializados
    site_searches = []
    for site in sites_relevantes[:5]:  # Limita a 5 sites para não sobrecarregar
        site_searches.extend([
            f'site:{site} "{titular}"',        # Empresa no site específico
            f'site:{site} {processo}',         # Processo com barra
            f'site:{site} {processo_clean}'    # Processo sem barra
        ])
    
    # Combina estratégias limitando quantidade para evitar rate limiting
    # Total: 3 básicas + 3 de impacto + 6 em sites = 12 buscas
    all_searches = basic_searches[:3] + impact_searches[:3] + site_searches[:6]
    
    print(f"\n  📍 Executando {len(all_searches)} buscas estratégicas...")
    
    # Executa cada busca com tratamento de erros e rate limiting
    for idx, search_query in enumerate(all_searches):
        try:
            # Adiciona delay aleatório entre buscas (exceto na primeira)
            # Isso evita ser bloqueado por fazer muitas requisições rápidas
            if idx > 0:
                time.sleep(random.uniform(1.5, 2.5))  # Entre 1.5 e 2.5 segundos
            
            # Executa a busca
            results = search_tool.run(search_query)
            
            # === PROCESSAMENTO PARA DUCKDUCKGO ===
            if isinstance(results, str) and results:
                # DuckDuckGo retorna string não estruturada
                
                # Tenta extrair URLs do texto
                urls_found = extract_urls_from_duckduckgo_text(results)
                
                if urls_found:
                    # Se encontrou URLs, cria uma entrada para cada uma
                    for url in urls_found[:3]:  # Máximo 3 URLs por busca
                        all_results.append({
                            'content': results[:500],  # Primeiros 500 caracteres
                            'query': search_query,     # Query que gerou o resultado
                            'link': url,              # URL extraída
                            'source': url,            # Duplica para compatibilidade
                            'title': f'Resultado de {search_query}',
                            'strategy': 'duckduckgo_extracted',
                            # Verifica se é de um site relevante
                            'is_relevant_site': any(site in url for site in sites_relevantes)
                        })
                else:
                    # Se não encontrou URLs, salva só o conteúdo
                    all_results.append({
                        'content': results[:500],
                        'query': search_query,
                        'source': f'Busca: {search_query}',
                        'link': '',  # Sem URL
                        'title': 'Resultado sem URL extraída',
                        'strategy': 'text_result',
                        'is_relevant_site': False
                    })
                    
            # === PROCESSAMENTO PARA GOOGLE SEARCH ===
            elif isinstance(results, list):
                # Google retorna lista de dicionários estruturados
                for item in results:
                    if isinstance(item, dict):
                        link = item.get('link', '')
                        
                        # Verifica se o link é de um site relevante
                        is_relevant_site = any(site in link for site in sites_relevantes)
                        
                        all_results.append({
                            'content': item.get('snippet', ''),  # Trecho do resultado
                            'title': item.get('title', ''),      # Título da página
                            'link': link,                        # URL
                            'source': link,                      # Duplica para compatibilidade
                            'query': search_query,               # Query usada
                            'is_relevant_site': is_relevant_site,
                            'strategy': 'structured_result'
                        })
                        
        except Exception as e:
            # Tratamento específico para rate limiting (erro 429)
            if "429" in str(e):
                print(f"  ⚠️ Rate limit atingido. Aguardando 5 segundos...")
                time.sleep(5)
            else:
                # Outros erros são logados mas não interrompem o processo
                logger.warning(f"  ⚠️ Erro na busca '{search_query}': {e}")
            continue
    
    # Ordena resultados priorizando sites relevantes
    # Sites como MPF, FUNAI, etc. aparecem primeiro
    all_results.sort(key=lambda x: x.get('is_relevant_site', False), reverse=True)
    
    print(f"  ✅ {len(all_results)} resultados encontrados")
    return all_results

def rag_summary_enhanced(query: str, search_tool, llm, embed_model, titular: str, processo: str, uf: str):
    """
    Implementa um sistema RAG (Retrieval-Augmented Generation) aprimorado.
    
    RAG combina busca de informações (Retrieval) com geração de texto (Generation)
    para criar resumos contextualizados baseados em fontes reais.
    
    Args:
        query (str): Query inicial de busca
        search_tool: Ferramenta de busca configurada
        llm: Modelo de linguagem (Gemini)
        embed_model: Modelo para criar embeddings de texto
        titular (str): Nome da empresa
        processo (str): Número do processo
        uf (str): Estado
        
    Returns:
        dict: Dicionário com resumo, fontes e descobertas relevantes
        
    Fluxo:
    1. Busca informações na web
    2. Cria embeddings dos documentos encontrados
    3. Usa o LLM para analisar e resumir com base no contexto
    4. Extrai e organiza as fontes citadas
    """
    print(f"\n🔍 Analisando: {processo} - {titular} ({uf})")
    
    # Executa busca aprimorada com todas as estratégias
    search_results = enhanced_search(titular, processo, uf, search_tool)
    
    # Verifica se encontrou resultados
    if not search_results:
        return {
            'summary': "Nenhuma informação encontrada na web para esta consulta.",
            'sources': [],
            'raw_findings': []
        }
    
    # === CRIAÇÃO DE DOCUMENTOS PARA O RAG ===
    docs = []  # Lista de documentos LangChain
    source_mapping = {}  # Mapeia IDs para resultados originais
    
    # Converte cada resultado de busca em um Document do LangChain
    for idx, result in enumerate(search_results):
        content = result.get('content', '')
        if content:
            doc_id = f"doc_{idx}"  # ID único para o documento
            
            # Cria documento com metadados completos
            docs.append(Document(
                page_content=content,  # Conteúdo textual
                metadata={
                    'doc_id': doc_id,
                    'source': result.get('link', result.get('source', 'Fonte não especificada')),
                    'title': result.get('title', ''),
                    'query': result.get('query', ''),
                    'link': result.get('link', '')  # URL quando disponível
                }
            ))
            source_mapping[doc_id] = result
    
    # Verifica se há documentos para processar
    if not docs:
        return {
            'summary': "Os resultados da busca não continham conteúdo processável.",
            'sources': [],
            'raw_findings': []
        }
    
    # === DIVISÃO DE DOCUMENTOS EM CHUNKS ===
    # Documentos muito longos são divididos em pedaços menores
    # para melhor processamento pelo modelo de embeddings
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,     # Tamanho máximo de cada chunk
        chunk_overlap=200    # Sobreposição entre chunks para manter contexto
    )
    docs_split = splitter.split_documents(docs)
    
    # === CRIAÇÃO DA BASE VETORIAL ===
    # Converte texto em vetores numéricos (embeddings) para busca semântica
    vect = Chroma.from_documents(docs_split, embed_model)
    
    # === TEMPLATE DO PROMPT ===
    # Define como o LLM deve analisar e estruturar a resposta
    enhanced_prompt_template = """
    Você é um analista especializado em mineração e impactos socioambientais. 
    Analise cuidadosamente o contexto fornecido sobre o processo minerário.
    
    **INSTRUÇÕES IMPORTANTES:**
    1. Extraia TODAS as informações relevantes do contexto, especialmente:
       - Tipo de minério e substâncias
       - Status atual do projeto (pesquisa, lavra, etc.)
       - Localização específica (município, coordenadas se disponível)
       - QUALQUER menção a impactos socioambientais, incluindo:
         * Sobreposição com Terras Indígenas (CITE O NOME DA TI)
         * Conflitos com comunidades tradicionais
         * Questões ambientais (desmatamento, poluição, etc.)
         * Ações do Ministério Público
         * Multas ou sanções ambientais
         * Acidentes ou incidentes
         * Protestos ou manifestações
    
    2. Para cada informação importante, indique de qual documento ela veio usando [Fonte: doc_X]
    
    3. Se encontrar informações sobre terras indígenas, comunidades afetadas ou impactos ambientais, 
       descreva-os em detalhes, não apenas mencione sua existência.
    
    **Contexto disponível:**
    {context}
    
    **Pergunta:** {question}
    
    **Resposta estruturada com citação das fontes:**
    """
    
    # Cria template com as variáveis necessárias
    PROMPT = PromptTemplate(
        template=enhanced_prompt_template,
        input_variables=["context", "question"]
    )
    
    # === CONFIGURAÇÃO DA CADEIA DE QA ===
    # RetrievalQA combina recuperação de documentos com geração de resposta
    qa_chain = RetrievalQA.from_chain_type(
        llm,  # Modelo Gemini
        retriever=vect.as_retriever(search_kwargs={"k": 8}),  # Busca top-8 chunks mais relevantes
        chain_type="stuff",  # Método que passa todos os docs de uma vez
        chain_type_kwargs={
            "prompt": PROMPT,
            "verbose": False  # Não mostra logs internos
        },
        return_source_documents=True  # Retorna os documentos usados na resposta
    )
    
    # === EXECUÇÃO DA ANÁLISE ===
    # Invoca a cadeia com a pergunta específica sobre o processo
    resposta = qa_chain.invoke({
        "query": f"Analise todas as informações sobre o processo {processo} da {titular}, especialmente impactos socioambientais"
    })
    
    # === EXTRAÇÃO DE FONTES ÚNICAS ===
    # Processa os documentos citados para extrair URLs únicas
    sources_with_metadata = []
    seen_urls = set()  # Evita duplicatas
    
    if 'source_documents' in resposta:
        for doc in resposta['source_documents']:
            # Tenta pegar o link dos metadados
            url = doc.metadata.get('link', '') or doc.metadata.get('source', '')
            
            # Adiciona apenas URLs válidas e únicas
            if url and url not in seen_urls and url.startswith('http'):
                seen_urls.add(url)
                sources_with_metadata.append({
                    'url': url,
                    'title': doc.metadata.get('title', ''),
                    'query': doc.metadata.get('query', '')
                })
    
    # === PROCESSAMENTO DE DESCOBERTAS RELEVANTES ===
    # Identifica e pontua resultados com base em palavras-chave de impacto
    raw_findings = []
    
    # Palavras-chave que indicam potenciais impactos socioambientais
    keywords = [
        'terra indígena', 'conflito', 'ameaça', 'impacto', 'ambiental', 
        'comunidade', 'protesto', 'multa', 'ação civil', 'ministério público',
        'sobreposição', 'desmatamento', 'poluição', 'contaminação'
    ]
    
    # Analisa cada resultado e atribui pontuação de relevância
    for result in search_results:
        content_lower = result.get('content', '').lower()
        
        # Sistema de pontuação
        score = 0
        
        # +10 pontos se for de site relevante (MPF, FUNAI, etc.)
        if result.get('is_relevant_site', False):
            score += 10
            
        # +1 ponto para cada palavra-chave encontrada
        score += sum(1 for keyword in keywords if keyword in content_lower)
        
        # Adiciona apenas resultados com pontuação > 0
        if score > 0:
            result['relevance_score'] = score
            raw_findings.append(result)
    
    # Ordena por relevância (maior pontuação primeiro)
    raw_findings.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    # Retorna estrutura completa com resumo, fontes e descobertas
    return {
        'summary': resposta['result'],  # Resumo gerado pelo LLM
        'sources': sources_with_metadata,  # URLs citadas
        'raw_findings': raw_findings[:5]  # Top-5 descobertas mais relevantes
    }

def format_report_section(processo: str, data: dict, row_data: dict):
    """
    Formata uma seção do relatório Markdown para um processo específico.
    
    Esta função é responsável pela apresentação visual dos dados,
    organizando as informações de forma clara e hierárquica.
    
    Args:
        processo (str): Número do processo
        data (dict): Dados da análise (resumo, fontes, descobertas)
        row_data (dict): Dados originais do shapefile
        
    Returns:
        str: Seção formatada em Markdown
    """
    # === CABEÇALHO DA SEÇÃO ===
    section = f"### 📋 Processo {processo}\n\n"
    
    # Informações básicas do processo
    section += f"**Titular:** {row_data[COL_TITULAR]}\n"
    section += f"**UF:** {row_data[COL_UF]}\n"
    section += f"**Área:** {row_data['area_ha_calculada']:.2f} hectares\n\n"
    
    # === RESUMO DA ANÁLISE ===
    section += "#### 📊 Análise do Contexto:\n"
    section += f"{data['summary'].strip()}\n\n"
    
    # === DESCOBERTAS SOBRE IMPACTOS ===
    if data.get('raw_findings'):
        section += "#### ⚠️ Descobertas Relevantes sobre Impactos:\n"
        
        # Lista até 5 descobertas mais relevantes
        for idx, finding in enumerate(data['raw_findings'][:5], 1):
            section += f"\n**Descoberta {idx}:**\n"
            
            # Conteúdo da descoberta (limitado a 500 caracteres)
            section += f"> {finding.get('content', '')[:500]}...\n"
            
            # Fonte da descoberta
            source = finding.get('link', finding.get('source', ''))
            if source and source.startswith('http'):
                # Se tem URL válida, cria link clicável
                title = finding.get('title', 'Link')
                section += f"> *Fonte: [{title}]({source})*\n"
                
                # Indica se é de site especializado
                if finding.get('is_relevant_site', False):
                    section += f"> 🎯 **Site especializado em impactos socioambientais**\n"
            else:
                # Se não tem URL, mostra a query usada
                section += f"> *Fonte: Busca via {finding.get('query', 'consulta web')}*\n"
    
    # === LISTA DE FONTES CONSULTADAS ===
    if data.get('sources'):
        section += "\n#### 🔗 Fontes Consultadas:\n"
        seen_urls = set()  # Evita URLs duplicadas
        valid_sources_count = 0
        
        for source in data['sources']:
            url = source.get('url', '')
            title = source.get('title', '')
            query = source.get('query', '')
            
            # Processa apenas URLs válidas e únicas
            if url and url not in seen_urls and url.startswith('http'):
                seen_urls.add(url)
                valid_sources_count += 1
                
                # Se não tem título, usa o domínio
                if not title or title == 'Fonte':
                    # Extrai domínio da URL (ex: www.exemplo.com)
                    title = url.split('/')[2] if len(url.split('/')) > 2 else 'Link'
                
                # Formata como link Markdown
                section += f"- [{title}]({url})"
                
                # Adiciona query se disponível
                if query:
                    section += f" *(busca: {query})*"
                section += "\n"
        
        # Se não encontrou URLs válidas, adiciona nota explicativa
        if valid_sources_count == 0:
            section += f"*Nota: As buscas foram realizadas via {SEARCH_ENGINE_USED} mas as URLs específicas não puderam ser extraídas.*\n"
    
    # Separador entre seções
    section += "\n---\n\n"
    return section

def main():
    """
    Função principal que orquestra todo o processo de análise.
    
    Esta função coordena todas as etapas do pipeline:
    1. Leitura do shapefile
    2. Seleção dos top-10 processos por área
    3. Busca de informações na web
    4. Análise com IA
    5. Geração de relatórios
    
    O fluxo é projetado para ser robusto, com tratamento de erros
    e feedback visual do progresso.
    """
    # Banner inicial
    print("🚀 INICIANDO ANÁLISE APRIMORADA DE CONTEXTO SIGMINE")
    print("=" * 60)

    # === ETAPA 1: LEITURA E PROCESSAMENTO DO SHAPEFILE ===
    try:
        print(f"\n📁 1. Lendo shapefile de: {SHAPEFILE_PATH}")
        
        # Lê o shapefile usando GeoPandas
        # GeoPandas estende pandas para trabalhar com dados geoespaciais
        sig = gpd.read_file(SHAPEFILE_PATH)
        print("   ✅ Shapefile lido com sucesso.")

        # === REPROJEÇÃO DO SISTEMA DE COORDENADAS ===
        # Converte para SIRGAS 2000 / Brazil Polyconic (EPSG:5880)
        # Isso é necessário para calcular áreas em metros quadrados
        # Sistemas de coordenadas geográficas (lat/lon) não permitem
        # cálculos de área precisos
        sig = sig.to_crs(5880)
        
        # === CÁLCULO DA ÁREA EM HECTARES ===
        # GeoPandas calcula área em m² para projeções métricas
        # Dividimos por 10.000 para converter m² em hectares
        sig["area_ha_calculada"] = sig.area / 10_000
        
        # === SELEÇÃO DOS TOP-10 PROCESSOS ===
        # Seleciona os 10 maiores processos minerários por área
        # Isso foca a análise nos processos mais significativos
        top10 = sig.nlargest(10, "area_ha_calculada").copy()
        
        # === ANÁLISE DE FREQUÊNCIA DE TITULARES ===
        # Identifica empresas que aparecem múltiplas vezes no top-10
        # Isso pode indicar grandes players no setor
        freq = (top10.groupby([COL_TITULAR], as_index=False)
                    .size()  # Conta ocorrências
                    .sort_values("size", ascending=False))  # Ordena por frequência
        
        # Filtra apenas titulares com mais de uma ocorrência
        freq_mais_1 = freq.query("size > 1")

        # === EXIBIÇÃO DOS RESULTADOS PRELIMINARES ===
        print("\n📊 Top-10 processos por área (em hectares):")
        # Mostra tabela com colunas selecionadas
        print(top10[[COL_PROCESSO, "area_ha_calculada", COL_TITULAR, COL_UF]].to_string())
        
        # Se houver titulares repetidos, mostra
        if not freq_mais_1.empty:
            print("\n🏢 Titulares que aparecem mais de uma vez no Top-10:")
            print(freq_mais_1.to_string())

    except Exception as e:
        # Tratamento de erros na leitura do shapefile
        # Erros comuns: arquivo não encontrado, formato inválido, colunas faltando
        print(f"❌ ERRO CRÍTICO ao ler ou processar o shapefile: {e}")
        return  # Encerra o programa se não conseguir ler os dados

    # === ETAPA 2: CONFIGURAÇÃO DAS FERRAMENTAS DE IA ===
    print("\n🤖 2. Configurando ferramentas de IA e busca...")
    
    # Configura ferramenta de busca (Google ou DuckDuckGo)
    search_tool = setup_search_tool()
    
    # === CONFIGURAÇÃO DO MODELO GEMINI ===
    # Gemini 2.5 Pro: modelo mais recente e capaz do Google
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",  # Versão do modelo
        temperature=0.1,         # Baixa temperatura = respostas mais consistentes
        max_output_tokens=2048   # Limite de tokens na resposta
    )
    
    # Modelo de embeddings para vetorização de texto
    # Usado para busca semântica nos documentos
    embed_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

    # === ETAPA 3: BUSCA E ANÁLISE DE CONTEXTO EXTERNO ===
    print("\n🔍 3. Iniciando busca aprimorada de contexto externo...")
    print("   Isso pode levar alguns minutos...")
    
    # Dicionário para armazenar contexto de cada processo
    contexto_proc = {}
    
    # === LOOP PRINCIPAL: ANÁLISE DE CADA PROCESSO ===
    # tqdm cria uma barra de progresso visual
    for _, row in tqdm(top10.iterrows(), total=len(top10), desc="Analisando Processos Top-10"):
        # Extrai dados do processo atual
        cod = row[COL_PROCESSO]      # Ex: "803237/2022"
        titular = row[COL_TITULAR]   # Ex: "VALE S.A."
        uf = row[COL_UF]            # Ex: "PA"
        
        # Query inicial simplificada
        # Não precisa ser complexa pois enhanced_search fará variações
        busca_inteligente = f'"{titular}" {uf}'
        
        # Executa análise RAG completa para o processo
        contexto_proc[cod] = rag_summary_enhanced(
            busca_inteligente,  # Query base
            search_tool,        # Ferramenta de busca
            llm,               # Modelo Gemini
            embed_model,       # Modelo de embeddings
            titular,           # Nome da empresa
            cod,               # Número do processo
            uf                 # Estado
        )
        
        # Adiciona dados originais do shapefile (convertidos para dict)
        # Necessário para serialização posterior
        contexto_proc[cod]['row_data'] = row.to_dict()

    # === ETAPA 4: ANÁLISE DE TITULARES RECORRENTES ===
    # Se houver empresas que aparecem múltiplas vezes
    contexto_emp = {}
    if not freq_mais_1.empty:
        print("\n🏢 4. Analisando perfil de titulares recorrentes...")
        
        # Análise específica para cada empresa recorrente
        for _, row in tqdm(freq_mais_1.iterrows(), total=len(freq_mais_1), desc="Analisando Titulares"):
            nome = row[COL_TITULAR]
            
            # Busca mais ampla sobre o perfil da empresa
            busca_empresa = f'"{nome}" mineradora perfil ambiental conflitos comunidades indígenas'
            
            contexto_emp[nome] = rag_summary_enhanced(
                busca_empresa,
                search_tool,
                llm,
                embed_model,
                nome,
                "Perfil Empresarial",  # Tipo genérico
                "Brasil"               # UF genérica
            )

    # === ETAPA 5: GERAÇÃO DO RELATÓRIO FINAL ===
    print("\n📝 5. Gerando relatório final aprimorado...")
    
    # Cria diretório de saída se não existir
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # === CONSTRUÇÃO DO RELATÓRIO MARKDOWN ===
    # Markdown é escolhido por ser legível, versionável e convertível
    relatorio_md = f"""# 📊 Relatório SIGMINE – Análise Aprimorada de Contexto com IA
    
**Data de Geração:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}  
**Modelo IA:** Google Gemini  
**Processos Analisados:** {len(top10)}  

---

## 🎯 Resumo Executivo

Este relatório apresenta uma análise detalhada dos {len(top10)} maiores processos minerários 
identificados no shapefile SIGMINE, com foco especial em impactos socioambientais, 
sobreposições com terras indígenas e conflitos com comunidades.

### ⚠️ Alertas Principais:
"""
    
    # === IDENTIFICAÇÃO DE PROCESSOS COM IMPACTOS ===
    # Analisa o resumo de cada processo procurando palavras-chave
    processos_com_impacto = []
    for cod, data in contexto_proc.items():
        summary_lower = data['summary'].lower()
        
        # Palavras que indicam potenciais impactos
        termos_impacto = ['terra indígena', 'conflito', 'impacto', 'ameaça']
        
        # Se encontrar qualquer termo, marca como processo com impacto
        if any(termo in summary_lower for termo in termos_impacto):
            processos_com_impacto.append(cod)
    
    # Adiciona alertas ao resumo executivo
    if processos_com_impacto:
        relatorio_md += f"\n- **{len(processos_com_impacto)} processos** com possíveis impactos socioambientais identificados\n"
        
        # Lista os 3 primeiros como exemplo
        for proc in processos_com_impacto[:3]:
            relatorio_md += f"  - Processo {proc}: Ver análise detalhada abaixo\n"
    else:
        relatorio_md += "\n- Nenhum impacto socioambiental significativo foi identificado nas fontes consultadas\n"
    
    # === SEÇÃO 1: ANÁLISE DETALHADA DOS PROCESSOS ===
    relatorio_md += "\n---\n\n## 📋 1. Análise Detalhada dos Processos Top-10\n\n"
    
    # Adiciona uma seção para cada processo
    for cod, data in contexto_proc.items():
        relatorio_md += format_report_section(cod, data, data['row_data'])

    # === SEÇÃO 2: PERFIL DOS TITULARES RECORRENTES ===
    if contexto_emp:
        relatorio_md += "\n## 🏢 2. Perfil dos Titulares Recorrentes\n\n"
        
        for nome, data in contexto_emp.items():
            relatorio_md += f"### {nome}\n\n"
            relatorio_md += f"{data['summary'].strip()}\n\n"
            
            # Lista fontes consultadas
            if data.get('sources'):
                relatorio_md += "**Fontes Consultadas:**\n"
                seen_urls = set()  # Evita duplicatas
                
                for source in data['sources']:
                    url = source.get('url', '')
                    title = source.get('title', 'Fonte')
                    
                    if url and url not in seen_urls and url.startswith('http'):
                        seen_urls.add(url)
                        relatorio_md += f"- [{title}]({url})\n"
                        
            relatorio_md += "\n---\n"

    # === NOTAS METODOLÓGICAS ===
    # Importante para transparência e reprodutibilidade
    relatorio_md += f"""
## 📌 Notas Metodológicas

- **Fonte dos dados espaciais:** Shapefile SIGMINE
- **Ferramentas de busca:** {SEARCH_ENGINE_USED}
- **Modelo de IA:** Google Gemini 2.5
- **Palavras-chave utilizadas:** mineração, impacto ambiental, terra indígena, conflito, comunidade

### 📄 Referências dos Documentos

As citações no formato [Fonte: doc_X] referem-se aos documentos recuperados durante a busca na web. Cada "doc_X" representa um trecho específico de conteúdo encontrado nas fontes consultadas. O mapeamento dos documentos é:

- **doc_1 a doc_N**: Trechos dos resultados de busca, ordenados pela relevância e pela presença em sites especializados
- **Sites prioritários**: terrasindigenas.org.br, mpf.mp.br, ibama.gov.br, funai.gov.br
- **Estratégias de busca**: Buscas básicas, buscas com termos de impacto, e buscas direcionadas a sites específicos

Para verificar a origem exata de cada citação:
1. Consulte a seção "Fontes Consultadas" em cada processo para ver as URLs dos sites pesquisados
2. O arquivo CSV "descobertas_impactos_detalhadas.csv" contém o conteúdo completo de cada descoberta com sua respectiva fonte
3. Os números dos documentos são atribuídos sequencialmente conforme os resultados são processados

### ⚠️ Limitações:
- As informações são baseadas em fontes públicas disponíveis na internet
- A ausência de menção a impactos não significa que eles não existam
- Recomenda-se verificação adicional com fontes oficiais (FUNAI, IBAMA, MPF)
- As referências [Fonte: doc_X] são internas ao sistema de processamento e podem variar entre execuções

---
*Relatório gerado automaticamente por sistema de análise SIGMINE com IA*
"""

    # === SALVAMENTO DO RELATÓRIO MARKDOWN ===
    with open(REPORT_FILENAME, "w", encoding="utf-8") as f:
        f.write(relatorio_md)

    # === GERAÇÃO DO CSV DE RESULTADOS ===
    # Cria estrutura tabular para análise em Excel/pandas
    csv_data = []
    
    for cod, data in contexto_proc.items():
        row_info = data.get('row_data', {})
        
        # === EXTRAÇÃO DE URLs VÁLIDAS ===
        # Tenta múltiplas fontes para garantir que captura URLs
        urls_fontes = []
        
        # Primeiro tenta pegar das sources (fontes citadas)
        for source in data.get('sources', []):
            url = source.get('url', '')
            if url and url.startswith('http'):
                urls_fontes.append(url)
        
        # Se não encontrou, tenta nos raw_findings
        if not urls_fontes:
            for finding in data.get('raw_findings', []):
                url = finding.get('link', '') or finding.get('source', '')
                if url and url.startswith('http') and url not in urls_fontes:
                    urls_fontes.append(url)
        
        # === CONSTRUÇÃO DA LINHA DO CSV ===
        csv_row = {
            'processo': cod,
            'titular': row_info.get(COL_TITULAR, ''),
            'uf': row_info.get(COL_UF, ''),
            'area_hectares': row_info.get('area_ha_calculada', 0),
            'resumo_analise': data.get('summary', '').replace('\n', ' ').strip(),  # Remove quebras de linha
            'possui_impacto_mencionado': 'Sim' if cod in processos_com_impacto else 'Não',
            'num_fontes_consultadas': len(urls_fontes),
            'fontes_urls': '; '.join(urls_fontes),  # Separa URLs com ponto-vírgula
            'data_analise': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'motor_busca': SEARCH_ENGINE_USED
        }
        
        # === EXTRAÇÃO DE DESCOBERTAS RELEVANTES ===
        # Pega os primeiros 200 caracteres das 3 descobertas mais relevantes
        descobertas = []
        for idx, finding in enumerate(data.get('raw_findings', [])[:3]):
            descobertas.append(finding.get('content', '')[:200])
        csv_row['descobertas_relevantes'] = ' | '.join(descobertas)  # Separa com pipe
        
        csv_data.append(csv_row)
    
    # === CRIAÇÃO E SALVAMENTO DO DATAFRAME ===
    df_resultados = pd.DataFrame(csv_data)
    csv_filename = os.path.join(OUTPUT_DIR, "analise_sigmine_resultados.csv")
    
    # encoding='utf-8-sig' adiciona BOM para compatibilidade com Excel
    df_resultados.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    
    # === GERAÇÃO DO CSV DETALHADO DE DESCOBERTAS ===
    # Este arquivo contém todas as descobertas com impactos, não resumidas
    descobertas_data = []
    
    for cod, data in contexto_proc.items():
        for finding in data.get('raw_findings', []):
            # Extrai URL válida
            url_encontrada = finding.get('link', '') or finding.get('source', '')
            if not url_encontrada.startswith('http'):
                url_encontrada = ''
            
            # Cria registro detalhado
            descobertas_data.append({
                'processo': cod,
                'titular': data.get('row_data', {}).get(COL_TITULAR, ''),
                'conteudo_descoberta': finding.get('content', ''),  # Conteúdo completo
                'fonte_url': url_encontrada,
                'titulo_fonte': finding.get('title', ''),
                'query_busca': finding.get('query', ''),  # Query que encontrou o resultado
                'site_relevante': 'Sim' if finding.get('is_relevant_site', False) else 'Não',
                'motor_busca': SEARCH_ENGINE_USED
            })
    
    # Salva CSV de descobertas se houver dados
    if descobertas_data:
        df_descobertas = pd.DataFrame(descobertas_data)
        descobertas_filename = os.path.join(OUTPUT_DIR, "descobertas_impactos_detalhadas.csv")
        df_descobertas.to_csv(descobertas_filename, index=False, encoding='utf-8-sig')
        print(f"✅ Descobertas detalhadas salvas em: '{descobertas_filename}'")
    
    # === MENSAGENS FINAIS ===
    print(f"\n✅ Relatório final salvo em: '{REPORT_FILENAME}'")
    print(f"✅ Resultados em CSV salvos em: '{csv_filename}'")
    print(f"✅ Motor de busca utilizado: {SEARCH_ENGINE_USED}")
    print("\n🎉 ANÁLISE CONCLUÍDA COM SUCESSO!")
    print("=" * 60)

# === PONTO DE ENTRADA DO PROGRAMA ===
# Este bloco só executa se o script for rodado diretamente
# Não executa se for importado como módulo
if __name__ == "__main__":
    main()