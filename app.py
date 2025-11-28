import streamlit as st
import sqlite3
import json
from typing import List, Dict, Set

# ==============================================================================
# 1. INFRAESTRUTURA DE BANCO DE DADOS (SQLITE)
# ==============================================================================

class DatabaseManager:
    def __init__(self, db_name="validrx.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()
        self.seed_data_if_empty()

    def create_tables(self):
        """Cria a estrutura do banco se não existir."""
        cursor = self.conn.cursor()
        
        # Tabela Medicamentos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medicamentos (
                id TEXT PRIMARY KEY,
                nome TEXT,
                principio_ativo TEXT,
                classe_terapeutica TEXT,
                familias_alergia TEXT, -- JSON
                concentracao_mg_ml REAL,
                min_idade_meses INTEGER,
                dose_max_diaria_adulto_mg REAL,
                contra_indicacoes TEXT, -- JSON
                vias_permitidas TEXT -- JSON
            )
        ''')

        # Tabela Regras Pediátricas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pediatria (
                medicamento_id TEXT PRIMARY KEY,
                modo TEXT,
                min REAL,
                max REAL,
                teto_dose REAL,
                FOREIGN KEY(medicamento_id) REFERENCES medicamentos(id)
            )
        ''')

        # Tabela Interações
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                substancia_a TEXT,
                substancia_b TEXT,
                nivel TEXT,
                mensagem TEXT
            )
        ''')
        self.conn.commit()

    def seed_data_if_empty(self):
        """Popula o banco com dados iniciais se estiver vazio (Bootstrapping)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT count(*) FROM medicamentos")
        if cursor.fetchone()[0] == 0:
            # Inserindo Adrenalina (Exemplo Crítico)
            self.add_drug(
                "MED_ADRE", "Adrenalina 1mg/mL", "epinefrina", "vasopressor", [],
                1.0, 0, 1.0, [], ["Intramuscular (IM)", "Endovenosa (IV)", "Subcutânea"],
                {"modo": "mg_kg_dose", "min": 0.01, "max": 0.01, "teto_dose": 0.5}
            )
            # Inserindo Amoxicilina
            self.add_drug(
                "MED_AMOX", "Amoxicilina Susp. 250mg/5ml", "amoxicilina", "antibiotico", ["penicilina"],
                50.0, 0, 3000.0, ["mononucleose"], ["Oral"],
                {"modo": "mg_kg_dia", "min": 40.0, "max": 50.0, "teto_dose": 0}
            )
            # Inserindo Ibuprofeno
            self.add_drug(
                "MED_IBUP", "Ibuprofeno Gotas 50mg/ml", "ibuprofeno", "aine", ["aines"],
                50.0, 6, 2400.0, ["dengue", "gastrite", "insuficiencia_renal"], ["Oral"],
                {"modo": "mg_kg_dose", "min": 5.0, "max": 10.0, "teto_dose": 400.0}
            )
            # Inserindo Varfarina
            self.add_drug(
                "MED_VARF", "Varfarina 5mg", "varfarina", "anticoagulante", ["cumarinicos"],
                0.0, 0, 15.0, ["hemorragia_ativa"], ["Oral"], None
            )
            
            # Inserindo Interação Clássica
            self.add_interaction("varfarina", "ibuprofeno", "ALTO", "🔴 RISCO HEMORRÁGICO: AINEs aumentam efeito da Varfarina.")
            print("Banco de dados populado com sucesso!")

    # --- MÉTODOS DE CADASTRO (BACKOFFICE) ---
    def add_drug(self, id, nome, principio, classe, alergias, conc, min_idade, max_adulto, contras, vias, ped_rule):
        cursor = self.conn.cursor()
        # Tratamento para concentração 0.0 (Comprimidos)
        conc_val = conc if conc > 0 else None
        
        cursor.execute('''
            INSERT OR REPLACE INTO medicamentos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (id, nome, principio, classe, json.dumps(alergias), conc_val, min_idade, max_adulto, json.dumps(contras), json.dumps(vias)))
        
        if ped_rule:
            cursor.execute('''
                INSERT OR REPLACE INTO pediatria VALUES (?, ?, ?, ?, ?)
            ''', (id, ped_rule['modo'], ped_rule['min'], ped_rule['max'], ped_rule.get('teto_dose', 0)))
        
        self.conn.commit()

    def add_interaction(self, sub_a, sub_b, nivel, msg):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO interacoes (substancia_a, substancia_b, nivel, mensagem) VALUES (?, ?, ?, ?)", 
                       (sub_a, sub_b, nivel, msg))
        self.conn.commit()

    # --- MÉTODOS DE LEITURA (CLÍNICO) ---
    def get_all_drugs_dict(self):
        """Reconstrói o dicionário completo para a Engine usar."""
        cursor = self.conn.cursor()
        drugs = {}
        
        cursor.execute("SELECT * FROM medicamentos")
        rows = cursor.fetchall()
        
        for r in rows:
            m_id = r[0]
            drug_obj = {
                "id": m_id, "nome": r[1], "principio_ativo": r[2], "classe_terapeutica": r[3],
                "familias_alergia": json.loads(r[4]), "concentracao_mg_ml": r[5],
                "min_idade_meses": r[6], "dose_max_diaria_adulto_mg": r[7],
                "contra_indicacoes": json.loads(r[8]), "vias_permitidas": json.loads(r[9]),
                "pediatria": None
            }
            # Busca regra pediatrica
            cursor.execute("SELECT * FROM pediatria WHERE medicamento_id = ?", (m_id,))
            ped = cursor.fetchone()
            if ped:
                drug_obj["pediatria"] = {
                    "modo": ped[1], "min": ped[2], "max": ped[3], "teto_dose": ped[4]
                }
            drugs[m_id] = drug_obj
            
        return drugs

    def get_interactions(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM interacoes")
        raw = cursor.fetchall()
        rules = []
        for r in raw:
            rules.append({
                "pair": {r[1], r[2]}, "level": r[3], "msg": r[4]
            })
        return rules

# ==============================================================================
# 2. ENGINE CLÍNICA (LÓGICA - Inalterada, só recebe dados)
# ==============================================================================
class ClinicalEngine:
    def __init__(self, drugs_dict, interactions_list):
        self.drugs = drugs_dict
        self.interactions = interactions_list

    def validate(self, patient, prescription):
        alerts = []
        drug = self.drugs.get(prescription['drug_id'])
        if not drug: return []

        # Variáveis
        weight = patient['weight_kg']
        age_months = patient['age_months']
        conditions = set(patient['conditions'])
        allergies = set(patient['allergies'])
        current_meds_ids = patient['current_meds']
        dose_input = prescription['dose_input']
        route = prescription['route']

        # Normalização de Dose
        dose_mg = dose_input * drug['concentracao_mg_ml'] if drug['concentracao_mg_ml'] else dose_input

        # --- VALIDACÕES ---
        # 1. Via
        if route not in drug['vias_permitidas']:
            alerts.append({"type": "BLOCK", "msg": f"⛔ ERRO DE VIA: {drug['nome']} só aceita {drug['vias_permitidas']}."})
        if "Adrenalina" in drug['nome'] and route == "Endovenosa (IV)" and "parada_cardiaca" not in conditions:
             alerts.append({"type": "BLOCK", "msg": "⛔ ERRO FATAL: Adrenalina IV só em PCR."})

        # 2. Idade
        if age_months < drug['min_idade_meses']:
            alerts.append({"type": "BLOCK", "msg": f"⛔ PROIBIDO PARA IDADE ({age_months} meses)."})

        # 3. Alergia
        match_alg = set(drug['familias_alergia']).intersection(allergies)
        if match_alg: alerts.append({"type": "BLOCK", "msg": f"⛔ ALERGIA A {list(match_alg)}."})

        # 4. Contraindicações
        match_cond = set(drug['contra_indicacoes']).intersection(conditions)
        if match_cond: alerts.append({"type": "BLOCK", "msg": f"⛔ CONTRAINDICADO PARA {list(match_cond)}."})

        # 5. Duplicidade
        existing_classes = {self.drugs[mid]['classe_terapeutica'] for mid in current_meds_ids if mid in self.drugs}
        if drug['classe_terapeutica'] in existing_classes:
            alerts.append({"type": "WARNING", "msg": f"⚠️ DUPLICIDADE: Classe {drug['classe_terapeutica']} já em uso."})

        # 6. Interações
        active_principles = {drug['principio_ativo']}
        for mid in current_meds_ids:
            if mid in self.drugs: active_principles.add(self.drugs[mid]['principio_ativo'])
        
        for rule in self.interactions:
            if rule['pair'].issubset(active_principles):
                alerts.append({"type": "BLOCK", "msg": rule['msg']})

        # 7. Posologia
        is_child = age_months < 144
        ped_rule = drug.get('pediatria')
        
        if is_child and ped_rule:
            # --- CORREÇÃO AQUI: ARREDONDAMENTO ---
            # Arredonda para 4 casas decimais para evitar o erro "0.2 > 0.2"
            min_dose = round(weight * ped_rule['min'], 4)
            max_dose = round(weight * ped_rule['max'], 4)
            
            # Calcula valor bruto
            raw_val = dose_mg if ped_rule['modo'] == 'mg_kg_dose' else (dose_mg * (24/prescription['freq']))
            val = round(raw_val, 4) # Arredonda o valor calculado também
            
            # Lógica de validação
            if 'teto_dose' in ped_rule and ped_rule['teto_dose'] > 0 and val > ped_rule['teto_dose']:
                alerts.append({"type": "BLOCK", "msg": f"⛔ TETO ABSOLUTO EXCEDIDO: {val}mg > {ped_rule['teto_dose']}mg."})
            elif val > max_dose:
                alerts.append({"type": "BLOCK", "msg": f"⛔ SOBREDOSE TÓXICA: {val}mg > {max_dose}mg."})
            elif val < min_dose:
                alerts.append({"type": "WARNING", "msg": f"⚠️ SUBDOSE: {val}mg < {min_dose}mg."})
        
        elif not is_child:
             # Arredonda adulto também
             val_adulto = round(dose_mg * (24/prescription['freq']), 4)
             if val_adulto > drug['dose_max_diaria_adulto_mg']:
                 alerts.append({"type": "BLOCK", "msg": "⛔ DOSE MÁXIMA ADULTO EXCEDIDA."})

        return alerts

# ==============================================================================
# 3. INTERFACE DE USUÁRIO (FRONT + BACKOFFICE)
# ==============================================================================
def main():
    st.set_page_config(page_title="ValidRx Commercial", layout="wide", page_icon="💊")
    
    # Inicializa Banco
    db = DatabaseManager()
    
    # Navegação
    menu = st.sidebar.radio("Navegação", ["🩺 Módulo Prescritor", "⚙️ Backoffice (Admin)"])

    if menu == "⚙️ Backoffice (Admin)":
        render_admin_panel(db)
    else:
        render_prescriber_panel(db)

def render_admin_panel(db):
    st.title("⚙️ Backoffice (Gestão de Regras)")
    
    tab_meds, tab_inter = st.tabs(["💊 Cadastrar Medicamentos", "⚠️ Cadastrar Interações"])

    # --- ABA 1: MEDICAMENTOS ---
    with tab_meds:
        st.subheader("Novo Medicamento")
        st.info("Preencha os dados abaixo. O sistema valida automaticamente conforme você digita.")
        
        # REMOVI O st.form PARA PERMITIR INTERATIVIDADE
        
        col1, col2 = st.columns(2)
        id_drug = col1.text_input("ID (Ex: MED_DEXA)", "").upper()
        nome = col2.text_input("Nome Comercial", "")
        principio = col1.text_input("Princípio Ativo", "").lower()
        classe = col2.text_input("Classe Terapêutica (p/ Duplicidade)", "").lower()
        
        conc = st.number_input("Concentração (mg/mL) - 0 se for comprimido", 0.0)
        min_idade = st.number_input("Idade Mínima (meses)", 0)
        max_adulto = st.number_input("Dose Máx Adulto (mg/dia)", 0.0)
        
        st.markdown("---")
        st.caption("🛡️ Camadas de Segurança")
        vias = st.multiselect("Vias Permitidas", ["Oral", "Endovenosa (IV)", "Intramuscular (IM)", "Subcutânea"])
        alergias = st.text_input("Famílias Alergia (ex: aines, penicilina)", "")
        contras = st.text_input("Contraindicações (ex: dengue, gastrite)", "")
        
        # --- AQUI ESTÁ A MÁGICA: CHECKBOX REATIVO ---
        st.markdown("---")
        st.caption("🧸 Regras Pediátricas")
        
        # Agora, ao clicar aqui, o Streamlit recarrega a tela e entra no IF abaixo
        tem_ped = st.checkbox("Habilitar modo pediátrico? (Cálculo mg/kg)")
        
        modo = "mg_kg_dose"
        p_min, p_max, p_teto = 0.0, 0.0, 0.0
        
        if tem_ped:
            st.success("Modo Pediátrico Ativado! Preencha os limites abaixo:")
            modo = st.selectbox("Modo de Cálculo", ["mg_kg_dose", "mg_kg_dia"])
            c1, c2, c3 = st.columns(3)
            p_min = c1.number_input("Mínimo (mg/kg)", 0.0)
            p_max = c2.number_input("Máximo (mg/kg)", 0.0)
            p_teto = c3.number_input("Teto Absoluto (mg)", 0.0)
        
        st.markdown("###")
        if st.button("💾 Salvar Medicamento", type="primary"):
            if not id_drug or not nome:
                st.error("ERRO: ID e Nome são obrigatórios.")
            else:
                lista_alergias = [x.strip().lower() for x in alergias.split(",") if x.strip()]
                lista_contras = [x.strip().lower() for x in contras.split(",") if x.strip()]
                
                rule = None
                if tem_ped:
                    rule = {"modo": modo, "min": p_min, "max": p_max, "teto_dose": p_teto}
                
                db.add_drug(id_drug, nome, principio, classe, lista_alergias, conc, min_idade, max_adulto, lista_contras, vias, rule)
                st.success(f"✅ Medicamento {nome} salvo com sucesso no Banco de Dados!")

    # --- ABA 2: INTERAÇÕES ---
    with tab_inter:
        st.subheader("Nova Regra de Interação")
        
        # Aqui mantivemos o form porque não tem campos condicionais complexos
        with st.form("add_interaction_form"):
            c1, c2 = st.columns(2)
            sub_a = c1.text_input("Substância A (Princípio Ativo)", "").lower()
            sub_b = c2.text_input("Substância B (Princípio Ativo)", "").lower()
            
            nivel = st.selectbox("Nível de Risco", ["ALTO (Bloquear)", "MEDIO (Avisar)"])
            msg = st.text_area("Mensagem de Alerta", "🔴 Risco de...")
            
            if st.form_submit_button("🔗 Criar Regra de Interação"):
                if not sub_a or not sub_b:
                    st.error("Preencha as duas substâncias.")
                else:
                    db.add_interaction(sub_a, sub_b, nivel, msg)
                    st.success(f"Regra entre {sub_a} e {sub_b} criada!")

        st.divider()
        st.write("📋 **Regras Cadastradas no Banco:**")
        regras = db.get_interactions()
        if not regras:
            st.caption("Nenhuma regra cadastrada ainda.")
        for r in regras:
            st.code(f"{list(r['pair'])} -> {r['msg']}")
            
def render_prescriber_panel(db):
    st.title("🩺 ValidRx: Prescrição Segura")
    
    # Carrega dados ATUALIZADOS do banco
    drugs_dict = db.get_all_drugs_dict()
    interactions = db.get_interactions()
    engine = ClinicalEngine(drugs_dict, interactions)
    
    # --- UI do Prescritor ---
    with st.sidebar:
        st.header("Dados do Paciente")
        weight = st.number_input("Peso (kg)", min_value=0.5, max_value=200.0, value=20.0, step=0.5)
        age = st.number_input("Idade (meses)", min_value=0, max_value=1200, value=60)
        
        st.subheader("Histórico Clínico")
        conds = st.multiselect("Condições", ["parada_cardiaca", "dengue", "insuficiencia_renal", "gastrite"])
        algs = st.multiselect("Alergias", ["penicilina", "aines", "dipirona"])
        
        # Selectbox de uso contínuo dinâmico
        drug_names = {v['nome']: k for k,v in drugs_dict.items()}
        in_use = st.multiselect("Em Uso (Já toma)", list(drug_names.keys()))
        in_use_ids = [drug_names[n] for n in in_use]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Detalhes da Prescrição")
        sel_name = st.selectbox("Medicamento", list(drug_names.keys()))
        sel_id = drug_names[sel_name]
        drug_data = drugs_dict[sel_id]
        
        # --- AJUSTE AQUI: INPUT DE DOSE SEGURO ---
        if drug_data['concentracao_mg_ml']:
            st.info(f"🧪 Líquido: {drug_data['concentracao_mg_ml']} mg/mL")
            # Value=1.0 para evitar viés de ancoragem (5ml era muito alto)
            dose = st.number_input("Dose (mL)", min_value=0.1, max_value=500.0, value=1.0, step=0.1)
        else:
            st.info("💊 Comprimido (Dose Fixa)")
            # Value=1.0 ou uma dose baixa segura
            dose = st.number_input("Dose (mg)", min_value=1.0, max_value=5000.0, value=1.0, step=1.0)
            
        # Adicionei 'Subcutânea' para compatibilidade com Adrenalina se necessário
        route = st.selectbox("Via de Administração", ["Oral", "Endovenosa (IV)", "Intramuscular (IM)", "Subcutânea"])
        freq = st.number_input("Frequência (a cada X horas)", min_value=1, max_value=48, value=8)
        
        st.markdown("---")
        if st.button("🔍 Validar Prescrição", type="primary"):
            pat = {"weight_kg": weight, "age_months": age, "conditions": conds, "allergies": algs, "current_meds": in_use_ids}
            presc = {"drug_id": sel_id, "dose_input": dose, "route": route, "freq": freq}
            
            alerts = engine.validate(pat, presc)
            
            with col2:
                st.subheader("Resultado da Análise")
                if not alerts: 
                    st.success("✅ **Prescrição Aprovada!**\n\nNenhum risco detectado para este paciente.")
                else:
                    st.error(f"⚠️ **Foram encontrados {len(alerts)} problemas:**")
                    for a in alerts:
                        if a['type'] == 'BLOCK': 
                            st.error(f"⛔ {a['msg']}")
                        else: 
                            st.warning(f"⚠️ {a['msg']}")

if __name__ == "__main__":
    main()