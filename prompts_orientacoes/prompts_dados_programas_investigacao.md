# prompts, dados e programas – investigando dados ambientais: compliance e anticorrupção

Este material compila **boas práticas** de uso de *large language models* (LLMs) e outras ferramentas de IA para acelerar apurações jornalísticas em meio ambiente, mineração e corrupção corporativa fileciteturn7file1.

---

## configuração recomendada – google ai studio

* **temperatura 0** – respostas determinísticas, ideais para fact‑checking fileciteturn7file1  
* **thinking mode** ativado – exibe raciocínio passo a passo  
* **grounding with google search** – reduz alucinações citando fontes fileciteturn7file1

> Ajuste a temperatura para 0,3‑0,7 quando precisar de *brainstorming* criativo fileciteturn7file1.

---

## deep research / investigação profunda

O recurso **Deep Research** transforma o modelo em um agente autônomo de busca fileciteturn7file1.  
Quando indisponível, simule o fluxo em três etapas:

1. **planejamento** – peça ao modelo para listar 3‑5 passos e fontes esperadas fileciteturn7file9  
2. **execução** – mande “execute o passo 1 e traga URLs”  
3. **síntese** – solicite relatório com até 8 parágrafos e citações completas

---

## chatgpt (o3‑pro / gpt‑4o)

* **temperatura 0–0,2**, browsing on, Advanced Data Analysis ligado para CSV/PDF fileciteturn7file5  
* peça “explique raciocínio, mas mostre só conclusão” para evitar prolixidade  
* modele prompts em cadeia (*chain‑of‑thought*) apenas em **modelos rápidos**; nos reflexivos, peça resumo fileciteturn7file12

---

## estrutura de prompt sugerida

```text
você é um repórter investigativo especializado em _______
contexto: (links, dados, metas)
tarefa: (lista de subtarefas)
formato de saída: markdown, tabelas simples
regras de qualidade: cite fontes, indique lacunas
```

Exemplo completo para o **Cadastro de Empregadores** (Lista Suja do Trabalho Escravo) está detalhado no PDF fileciteturn7file17.

---

## prompts para análise de shapefiles do sigmine

O documento inclui prompt comentado para gerar, com GeoPandas, estatísticas de **processos minerários ativos** a partir do shapefile *BRASIL.shp* (SIGMINE) fileciteturn7file6:

* reprojetar para **EPSG:5880**  
* calcular contagem, área total/mediana  
* listar top‑10 processos por área  
* tabela de distribuição por UF e FASE

---

## onde economizar sem perder qualidade

* use **gpt‑3.5‑turbo** para raspagem e parsing em massa; reserve o **o3‑pro** para sínteses finais fileciteturn7file5  
* ative cache de tokens para consultas repetidas fileciteturn7file5

---

## links úteis

* **Combate ao trabalho escravo** – portal MTE fileciteturn7file12  
* **Pinpoint / Journalist Studio** – busca em acervos PDF fileciteturn7file12  
* **SIGMINE processos minerários** – dados.gov.br fileciteturn7file6  
* **Cadastro Mineiro SCM** – microdados ANM fileciteturn7file6  

---

## conclusão

Ferramentas de IA potencializam a investigação, mas exigem **configuração adequada, prompts claros e verificação rigorosa** para evitar erros e alucinações. As sugestões aqui servem como ponto de partida para fluxos híbridos que combinam scraping, bases abertas e modelos avançados.
