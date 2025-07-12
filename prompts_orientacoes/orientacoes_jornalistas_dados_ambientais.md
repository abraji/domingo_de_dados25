# orientações práticas para jornalistas investigativos em dados ambientais

## introdução

Com base nos problemas e soluções mapeados no relatório *Dados abertos e combate a crimes ambientais*, este guia apresenta **10 orientações** para jornalistas que pretendem usar bases públicas abertas em investigações ambientais.  
As dicas focam em contornar limitações frequentes – como ausência de metadados, dificuldade de download e formatação inadequada – e em **aproveitar ao máximo os dados disponíveis** fileciteturn7file0.

---

## 10 orientações práticas

1. **verifique a atualidade dos dados** – checar a data de atualização da base e acionar LAI ou órgão gestor quando necessário fileciteturn7file0  
2. **avalie a completude e cruze fontes** para suprir lacunas (ex.: usar satélites quando faltam coordenadas) fileciteturn7file0  
3. **utilize scraping ou scripts** para coletar dados em lote quando não existe download único fileciteturn7file0  
4. **converta arquivos** para formatos abertos (CSV, GeoJSON) antes de analisar fileciteturn7file0  
5. **cheque licenças e seja transparente** quanto à origem e eventuais restrições fileciteturn7file0  
6. **busque / construa documentação** e mantenha um glossário dos campos fileciteturn7file0  
7. **escolha ferramentas adequadas** (QGIS, GeoPandas, Earth Engine, no‑code) conforme o tipo de dado fileciteturn7file0  
8. **atenção redobrada a dados espaciais** – projeção, datum, interseções precisas fileciteturn7file19  
9. **documente todas as etapas** de limpeza e transformação para reprodutibilidade fileciteturn7file7  
10. **explore cruzamentos criativos, mas valide** achados com fontes locais e imagens de alta resolução fileciteturn7file7

---

## exemplos de pautas investigativas

O documento sugere **10 investigações possíveis** usando cruzamentos de bases abertas fileciteturn7file2. Abaixo um resumo dos cinco primeiros exemplos (consulte o PDF para a lista completa):

| # | tema | bases principais | técnicas chave |
|---|------|-----------------|----------------|
| 1 | quem são os donos do desmatamento ilegal? | PRODES, CAR (e SNCR opcional) | sobreposição de polígonos, agregação por propriedade fileciteturn7file2 |
| 2 | desmatamento autorizado vs. ilegal | SINAFLOR (ASV/ASUS), DETER/PRODES | join espacial + filtro temporal |
| 3 | rota da madeira | DOF – transportes & Autex, PRODES | análise de redes, sankey, comparação volume autorizado × transportado |
| 4 | garimpo ilegal x concessões | SIGMINE, DETER mineração, TIs/UCs | seleção espacial fora de concessão, hotspots em áreas protegidas |
| 5 | tráfico de fauna | autos de infração Ibama (fauna), SISFAUNA | geocodificação de ocorrências, mapa de calor fileciteturn7file4 |

*(Os demais exemplos 6‑10 cobrem agrotóxicos proibidos, reincidentes ambientais, fiscalização estadual vs federal, grilagem digital e intersecção trabalho escravo + desmatamento.)* fileciteturn7file8 fileciteturn7file10

---

## conclusão

Seguindo estas orientações e exemplos, repórteres conseguem **driblar obstáculos** e revelar histórias escondidas nos dados públicos. A chave é a combinação de persistência técnica, criatividade investigativa e rigor na validação fileciteturn7file7.
