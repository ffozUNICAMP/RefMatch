import tempfile
import streamlit as st



#CONFIGURAÇÕES INICIAIS
st.set_page_config(
    layout='wide',
    page_title='RefMatch - SBU',
    page_icon=':purple_heart:'
)


# ---- HEADER COM TÍTULO + LOGO ----
col1, col2 = st.columns([10, 2])

# TÍTULO DO APP

with col1:
    st.title('RefMatch - SBU :purple_heart::books:',anchor='string')
    st.header('Análise automática de referências de planos de ensino ao acervo',anchor=False)

with col2:
    st.image("https://gesec.sbu.unicamp.br/wp-content/uploads/sites/68/2025/11/SBU_Fundo_Branco-JPEG.jpg", width=160)  # ajuste o path e o tamanho conforme necessário

st.markdown("&nbsp;")

# PREÂMBULO
st.write('''
        Bem-vindo ao RefMatch, uma aplicação desenvolvida para verificar automaticamente as referências bibliográficas 
        presentes em planos de ensino e identificar a disponibilidade desses materiais no acervo do Sistema de Bibliotecas da Unicamp.
        ''')

st.write('''
        O RefMatch foi projetado para oferecer um apoio rápido, objetivo e consistente à análise bibliográfica de planos de ensino, 
        simplificando a verificação do acervo e auxiliando na tomada de decisões sobre atualização, adequação e desenvolvimento de coleções.
        ''')
st.markdown("&nbsp;")

st.write('''
        **Como usar:**
        1. **Insira a API Key:** No campo indicado, informe sua chave de API para habilitar o processamento das referências.
        2. **Selecione a unidade:** Escolha a unidade responsável pelo plano de ensino.
        3. **Faça o upload do arquivo:** Envie o plano de ensino em formato PDF (preferencialmente com OCR). O sistema extrairá as referências automaticamente.
        4. **Visualização dos resultados:** ALTERAR
        ''')
st.divider()
st.markdown("&nbsp;")

# INPUT DE DADOS
api_key = st.text_input('Insira sua API Key do Gemini', 'AIpsS0AfgGsD3Pd3g_dfrvUsdL78L7u8LM_md-cg')
unidade = st.selectbox('Selecione a unidade:',
                       ['IFCH']
                       )
uploaded_file = st.file_uploader('Faça o upload do arquivo:', type=['pdf'], accept_multiple_files=False)

st.markdown('&nbsp;&nbsp;')
st.divider()

st.markdown('''
    Elaborado pelo [Sistema de Bibliotecas da Unicamp - SBU](https://www.sbu.unicamp.br/sbu/)  
''')
