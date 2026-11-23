
import streamlit as st
import pandas as pd
import unicodedata
import re
from io import StringIO, BytesIO
from pathlib import Path
from rapidfuzz import process, fuzz
from google import genai
from google.genai import types
import openpyxl


# =====================================================
# CONFIGURAÇÕES INICIAIS
# =====================================================

st.set_page_config(
    layout="wide",
    page_title="RefMatch - SBU",
    page_icon="💜"
)


# =====================================================
# FUNÇÕES DE PROCESSAMENTO
# =====================================================

PROMPT = """
Você receberá o texto completo de uma ementa de disciplina,
que pode conter referências bibliográficas em qualquer parte.

Sua tarefa é extrair todas as referências bibliográficas
que realmente aparecem no texto, sem criar, inferir ou
completar nenhuma informação ausente.

A resposta deve conter apenas CSV separado por PIPE (|).

Identifique todas as referências, mesmo fora da seção
Bibliografia.

Não adicione informações ausentes.
Quando faltar informação, preencha com NaN.
Evite duplicatas.
Registre as ocorrências no campo Localização no texto.

Formate edições como 11. ed.
Transcreva o ISBN exatamente como aparece.

Tipos de referência:
Livro
Capítulo de livro
Artigo
Artigo de evento
Tese/Dissertação
Legislação
Site
Patente
Filme/Vídeo
Documento sonoro
Partitura
NaN

Quando houver "In:", classifique como Capítulo de livro
somente quando for um trecho de uma obra maior.
Nesse caso, use os autores/organizadores da obra principal
no campo Autor(es) e o título da obra principal no campo Título.

Cabeçalho obrigatório:

Nº|Tipo de referência|Autor(es)|Título|Edição|Ano|Editora / Fonte|Local (cidade)|ISBN|Observações|Localização no texto

Não apresente comentários, explicações ou formatação Markdown.
Retorne somente o CSV.
"""


def extrair_referencias_pdf(pdf_bytes, api_key):

    client = genai.Client(api_key=api_key)

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(
                    data=pdf_bytes,
                    mime_type="application/pdf"
                ),
                types.Part.from_text(text=PROMPT),
            ],
        ),
    ]

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=contents,
    )

    if not response.text:
        raise ValueError("O Gemini não retornou referências.")

    return response.text


def converter_csv(resultado):

    # Remove eventuais marcadores Markdown
    resultado = resultado.replace("```csv", "")
    resultado = resultado.replace("```", "").strip()

    # Localiza o cabeçalho esperado
    linhas = resultado.splitlines()

    indice = next(
        (
            i for i, linha in enumerate(linhas)
            if linha.strip().startswith("Nº|Tipo de referência")
        ),
        None
    )

    if indice is None:
        raise ValueError(
            "Não foi possível localizar o cabeçalho do CSV."
        )

    resultado = "\n".join(linhas[indice:])

    df = pd.read_csv(
        StringIO(resultado),
        sep="|",
        dtype=str
    )

    df.columns = df.columns.str.strip()

    df = df.apply(
        lambda col: col.str.strip()
        if col.dtype == "object" else col
    )

    # Padronização utilizada no notebook
    df = df.apply(
        lambda col: col.str.upper()
        if col.dtype == "object" else col
    )

    return df


# =====================================================
# FUNÇÕES DE COMPARAÇÃO COM O ACERVO
# =====================================================

def normalizar_texto(texto):

    if pd.isna(texto):
        return ""

    texto = unicodedata.normalize("NFKD", str(texto))

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = texto.upper().strip()

    texto = re.sub(r"[^\w\s]", "", texto)

    texto = re.sub(r"\s+", " ", texto)

    return texto


def extrair_primeiro_autor(autor):

    if pd.isna(autor):
        return ""

    return autor.split(";")[0].strip()


@st.cache_data
def carregar_base(caminho):

    base = pd.read_csv(
        caminho,
        sep="|",
        skipfooter=1,
        engine="python",
        dtype=str
    )

    base.columns = [
        "Material",
        "Título",
        "Autor",
        "Código título",
        "URL Detalhe",
        "Classificação",
        "PHA",
        "Edição",
        "Ano",
        "ISBN",
        "Tombo",
        "Biblioteca",
        "Status"
    ]

    return base


def enriquecer_referencias(df_ref, df_base):

    df_ref = df_ref.copy()
    df_base = df_base.copy()

    # Normalização dos títulos
    df_ref["titulo_norm"] = (
        df_ref["Título"].apply(normalizar_texto)
    )

    df_base["titulo_norm"] = (
        df_base["Título"].apply(normalizar_texto)
    )

    # Normalização dos autores
    df_ref["autor_norm"] = (
        df_ref["Autor(es)"].apply(normalizar_texto)
    )

    df_base["autor_norm"] = (
        df_base["Autor"].apply(normalizar_texto)
    )

    df_ref["autor_main"] = (
        df_ref["autor_norm"].apply(extrair_primeiro_autor)
    )

    df_base["autor_main"] = (
        df_base["autor_norm"].apply(extrair_primeiro_autor)
    )

    titulos_base = df_base["titulo_norm"].unique()

    resultados = []

    for _, ref in df_ref.iterrows():

        titulo_ref = ref["titulo_norm"]
        autor_ref = ref["autor_main"]

        encontrou = False
        linhas_adicionadas = 0

        if titulo_ref and titulos_base.size:

            match = process.extractOne(
                titulo_ref,
                titulos_base,
                scorer=fuzz.ratio
            )

            if match:

                titulo_match = match[0]
                score_titulo = match[1]

                # Tratamento de títulos parciais
                if "..." in str(ref["Título"]):

                    match = process.extractOne(
                        titulo_ref,
                        titulos_base,
                        scorer=fuzz.partial_ratio
                    )

                    if match:
                        titulo_match = match[0]
                        score_titulo = match[1]

                if score_titulo >= 80:

                    df_matches = df_base[
                        df_base["titulo_norm"] == titulo_match
                    ]

                    for _, base in df_matches.iterrows():

                        if fuzz.ratio(
                            autor_ref,
                            base["autor_main"]
                        ) >= 70:

                            nova_linha = ref.drop(
                                [
                                    "titulo_norm",
                                    "autor_norm",
                                    "autor_main"
                                ]
                            ).to_dict()

                            nova_linha.update({
                                "URL Detalhe": base["URL Detalhe"],
                                "Edição_base": base["Edição"],
                                "Ano_base": base["Ano"],
                                "Biblioteca": base["Biblioteca"],
                                "Status": base["Status"]
                            })

                            resultados.append(nova_linha)

                            encontrou = True
                            linhas_adicionadas += 1

        flag_acervo = "SIM" if encontrou else "NÃO"

        if encontrou:

            for i in range(
                len(resultados) - linhas_adicionadas,
                len(resultados)
            ):
                resultados[i]["Disponível no acervo"] = flag_acervo

        else:

            nova_linha = ref.drop(
                [
                    "titulo_norm",
                    "autor_norm",
                    "autor_main"
                ]
            ).to_dict()

            nova_linha.update({
                "URL Detalhe": None,
                "Edição_base": None,
                "Ano_base": None,
                "Biblioteca": None,
                "Status": None,
                "Disponível no acervo": flag_acervo
            })

            resultados.append(nova_linha)

    return pd.DataFrame(resultados)


# =====================================================
# INTERFACE
# =====================================================

# HEADER

col1, col2 = st.columns([10, 2])

with col1:

    st.title(
        "RefMatch - SBU :purple_heart::books:",
        anchor=False
    )

    st.header(
        "Análise automática de referências de planos de ensino ao acervo",
        anchor=False
    )

with col2:

    st.image(
        "https://gesec.sbu.unicamp.br/wp-content/uploads/sites/68/2025/11/SBU_Fundo_Branco-JPEG.jpg",
        width=160
    )


st.markdown("&nbsp;")

st.write("""
Bem-vindo ao RefMatch, uma aplicação desenvolvida para
verificar automaticamente as referências bibliográficas
presentes em planos de ensino e identificar a disponibilidade
desses materiais no acervo do Sistema de Bibliotecas da Unicamp.
""")

st.write("""
O RefMatch oferece apoio à análise bibliográfica de planos
de ensino, simplificando a verificação do acervo e auxiliando
na tomada de decisões sobre atualização, adequação e
desenvolvimento de coleções.
""")

st.markdown("&nbsp;")

st.markdown("""
**Como usar:**

1. Informe sua API Key do Gemini.
2. Selecione a unidade responsável pelo plano de ensino.
3. Faça o upload do arquivo PDF.
4. Clique em **Executar análise**.
5. Consulte os resultados e baixe o relatório.
""")

st.divider()


# =====================================================
# ENTRADA DE DADOS
# =====================================================

api_key = st.text_input(
    "Insira sua API Key do Gemini",
    type="password",
    help="Sua chave será utilizada para realizar a extração das referências."
)

unidade = st.selectbox(
    "Selecione a unidade:",
    ["IFCH"]
)

uploaded_file = st.file_uploader(
    "Faça o upload do plano de ensino:",
    type=["pdf"],
    accept_multiple_files=False
)

st.markdown("&nbsp;")


# =====================================================
# BOTÃO DE EXECUÇÃO
# =====================================================

executar = st.button(
    "▶ Executar análise",
    type="primary",
    use_container_width=True
)


if executar:

    if not api_key:

        st.warning("Informe sua API Key do Gemini.")

    elif uploaded_file is None:

        st.warning("Faça o upload de um arquivo PDF.")

    else:

        try:

            # Localização da base da unidade
            caminho_base = (
                Path(__file__).parent /
                f"base_{unidade}.csv"
            )

            if not caminho_base.exists():

                st.error(
                    f"Base bibliográfica não encontrada: {caminho_base.name}"
                )

                st.stop()

            with st.spinner(
                "Extraindo referências bibliográficas com Gemini..."
            ):

                pdf_bytes = uploaded_file.getvalue()

                resultado = extrair_referencias_pdf(
                    pdf_bytes,
                    api_key
                )

            with st.spinner(
                "Organizando referências bibliográficas..."
            ):

                df_referencias = converter_csv(resultado)

            if df_referencias.empty:

                st.warning(
                    "Nenhuma referência foi identificada no documento."
                )

                st.stop()

            with st.spinner(
                "Consultando a base bibliográfica do acervo..."
            ):

                base = carregar_base(str(caminho_base))

                df_resultado = enriquecer_referencias(
                    df_referencias,
                    base
                )

            # Guarda os resultados na sessão
            st.session_state["resultado"] = df_resultado
            st.session_state["unidade"] = unidade

            st.success("Análise concluída com sucesso!")

        except Exception as e:

            st.error(
                f"Ocorreu um erro durante o processamento: {e}"
            )


# =====================================================
# APRESENTAÇÃO DOS RESULTADOS
# =====================================================

if "resultado" in st.session_state:

    df_resultado = st.session_state["resultado"]

    st.divider()

    st.subheader("Resultados da análise")

    total = len(df_resultado)

    disponiveis = (
        df_resultado["Disponível no acervo"] == "SIM"
    ).sum()

    indisponiveis = (
        df_resultado["Disponível no acervo"] == "NÃO"
    ).sum()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Referências identificadas",
        total
    )

    col2.metric(
        "Disponíveis no acervo",
        disponiveis
    )

    col3.metric(
        "Não localizadas",
        indisponiveis
    )

    st.markdown("&nbsp;")

    # Filtro de disponibilidade
    filtro = st.selectbox(
        "Filtrar resultados:",
        [
            "Todas as referências",
            "Disponíveis no acervo",
            "Não localizadas"
        ]
    )

    if filtro == "Disponíveis no acervo":

        df_exibicao = df_resultado[
            df_resultado["Disponível no acervo"] == "SIM"
        ]

    elif filtro == "Não localizadas":

        df_exibicao = df_resultado[
            df_resultado["Disponível no acervo"] == "NÃO"
        ]

    else:

        df_exibicao = df_resultado

    st.dataframe(
        df_exibicao,
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL Detalhe": st.column_config.LinkColumn(
                "Consultar no Acervus",
                display_text="Acessar registro"
            )
        }
    )


    # =====================================================
    # EXPORTAÇÃO DOS RESULTADOS
    # =====================================================

    df_exportacao = st.session_state["resultado"].copy()

    # Exportação CSV com codificação compatível com Excel
    csv = df_exportacao.to_csv(
        index=False,
        sep=";",
        na_rep=""
    ).encode("utf-8-sig")

    # Exportação Excel
    excel_buffer = BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        df_exportacao.to_excel(
            writer,
            index=False,
            sheet_name="Resultado"
        )

    # Botões lado a lado
    col1, col2 = st.columns(2)

    with col1:

        st.download_button(
            label="📥 Baixar resultado em CSV",
            data=csv,
            file_name="resultado_refmatch.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:

        st.download_button(
            label="📊 Baixar resultado em Excel",
            data=excel_buffer.getvalue(),
            file_name="resultado_refmatch.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )



# =====================================================
# RODAPÉ
# =====================================================

st.divider()

st.markdown("""
Elaborado pelo [Sistema de Bibliotecas da Unicamp (SBU)](
https://www.sbu.unicamp.br/sbu/
)
""")
