import streamlit as st
from typing import List, Dict, Set, Optional

# ==============================================================================
# 1. CAMADA DE DADOS (REPOSITORY) - AGORA COM "VIAS PERMITIDAS"
# ==============================================================================

class DrugRepository:
    def __init__(self):
        self.drugs = {
            "MED_AMOX": {
                "id": "MED_AMOX",
                "nome": "Amoxicilina Susp. 250mg/5ml",
                "principio_ativo": "amoxicilina",
                "classe_terapeutica": "antibiotico",
                "familias_alergia": ["penicilina", "betalactamico"],
                "concentracao_mg_ml": 50.0,
                "min_idade_meses": 0,
                "dose_max_diaria_adulto_mg": 3000.0,
                "contra_indicacoes": ["mononucleose"],
                "vias_permitidas": ["Oral"],  # CAMADA 7
                "pediatria": {
                    "modo": "mg_kg_dia",
                    "min": 40.0,
                    "max": 50.0
                }
            },
            "MED_IBUP": {
                "id": "MED_IBUP",
                "nome": "Ibuprofeno Gotas 50mg/ml",
                "principio_ativo": "ibuprofeno",
                "classe_terapeutica": "aine",
                "familias_alergia": ["aines"],
                "concentracao_mg_ml": 50.0,
                "min_idade_meses": 6,
                "dose_max_diaria_adulto_mg": 2400.0,
                "contra_indicacoes": ["dengue", "varicela", "insuficiencia_renal", "gastrite"],
                "vias_permitidas": ["Oral"],
                "pediatria": {
                    "modo": "mg_kg_dose",
                    "min": 5.0,
                    "max": 10.0,
                    "teto_dose": 400.0
                }
            },
            "MED_DIP": {
                "id": "MED_DIP",
                "nome": "Dipirona Gotas 500mg/ml",
                "principio_ativo": "dipirona",
                "classe_terapeutica": "analgesico",
                "familias_alergia": ["dipirona", "pirazolonas"],
                "concentracao_mg_ml": 500.0,
                "min_idade_meses": 3,
                "dose_max_diaria_adulto_mg": 4000.0,
                "contra_indicacoes": [],
                "vias_permitidas": ["Oral", "Endovenosa (IV)", "Intramuscular (IM)"],
                "pediatria": {
                    "modo": "mg_kg_dose",
                    "min": 10.0,
                    "max": 25.0,
                    "teto_dose": 1000.0
                }
            },
            "MED_ADRE": {  # ADICIONADO: ADRENALINA
                "id": "MED_ADRE",
                "nome": "Adrenalina (Epinefrina) 1mg/mL",
                "principio_ativo": "epinefrina",
                "classe_terapeutica": "vasopressor",
                "familias_alergia": [],
                "concentracao_mg_ml": 1.0,
                "min_idade_meses": 0,
                "dose_max_diaria_adulto_mg": 1.0, 
                "contra_indicacoes": [],
                "vias_permitidas": ["Intramuscular (IM)", "Endovenosa (IV)", "Subcutânea"],
                "pediatria": {
                    "modo": "mg_kg_dose",
                    "min": 0.01,
                    "max": 0.01, # Dose estrita
                    "teto_dose": 0.5 # Teto absoluto
                }
            },
            "MED_DICLO": {
                "id": "MED_DICLO",
                "nome": "Diclofenaco Potássico 50mg",
                "principio_ativo": "diclofenaco",
                "classe_terapeutica": "aine",
                "familias_alergia": ["aines"],
                "concentracao_mg_ml": None, # Comprimido
                "min_idade_meses": 168, 
                "dose_max_diaria_adulto_mg": 150.0,
                "contra_indicacoes": ["insuficiencia_renal", "hipertensao", "dengue"],
                "vias_permitidas": ["Oral"],
                "pediatria": None
            },
            "MED_VARF": {
                "id": "MED_VARF",
                "nome": "Varfarina 5mg",
                "principio_ativo": "varfarina",
                "classe_terapeutica": "anticoagulante",
                "familias_alergia": ["cumarinicos"],
                "concentracao_mg_ml": None,
                "min_idade_meses": 0,
                "dose_max_diaria_adulto_mg": 15.0,
                "contra_indicacoes": ["hemorragia_ativa"],
                "vias_permitidas": ["Oral"],
                "pediatria": None
            }
        }

        self.interactions = [
            {
                "pair": {"varfarina", "ibuprofeno"},
                "level": "ALTO",
                "msg": "🔴 RISCO HEMORRÁGICO: AINEs aumentam o efeito da Varfarina."
            },
            {
                "pair": {"ibuprofeno", "diclofenaco"},
                "level": "MEDIO",
                "msg": "⚠️ DUPLICIDADE TÓXICA: Associação de dois AINEs aumenta risco renal."
            }
        ]

    def get_drug(self, drug_id: str) -> dict:
        return self.drugs.get(drug_id)

    def get_all_drugs_list(self) -> dict:
        return {v['nome']: k for k, v in self.drugs.items()}

    def check_interaction(self, active_principles: Set[str]) -> List[str]:
        alerts = []
        for rule in self.interactions:
            if rule['pair'].issubset(active_principles):
                alerts.append(f"{rule['msg']}")
        return alerts


# ==============================================================================
# 2. CAMADA DE NEGÓCIO (ENGINE COM 7 CAMADAS)
# ==============================================================================

class ClinicalEngine:
    def __init__(self, repository: DrugRepository):
        self.repo = repository

    def validate_prescription(self, patient_profile: dict, prescription_item: dict) -> List[dict]:
        alerts = []
        drug = self.repo.get_drug(prescription_item['drug_id'])
        if not drug: return []

        # Dados
        age_months = patient_profile['age_months']
        weight = patient_profile['weight_kg']
        conditions = set(patient_profile['conditions'])
        allergies = set(patient_profile['allergies'])
        current_meds_ids = patient_profile['current_meds']
        
        dose_input = prescription_item['dose_input']
        freq = prescription_item['freq_hours']
        route = prescription_item['route'] # Nova variável
        
        # Conversão ML -> MG
        dose_mg = 0.0
        if drug['concentracao_mg_ml']:
            dose_mg = dose_input * drug['concentracao_mg_ml']
        else:
            dose_mg = dose_input
        
        # Regra Fatal da Adrenalina
        if "Adrenalina" in drug['nome'] and route == "Endovenosa (IV)" and "parada_cardiaca" not in conditions:
             alerts.append({"type": "BLOCK", "msg": "⛔ ERRO FATAL DE VIA: Adrenalina Endovenosa Pura é restrita para Parada Cardíaca. Use INTRAMUSCULAR."})

        # --- CAMADA 1: IDADE ---
        if age_months < drug['min_idade_meses']:
            alerts.append({"type": "BLOCK", "msg": f"⛔ PROIBIDO PARA IDADE ({age_months} meses). Mínimo: {drug['min_idade_meses']} meses."})

        # --- CAMADA 2: ALERGIAS ---
        drug_families = set(drug['familias_alergia'])
        match_allergy = drug_families.intersection(allergies)
        if match_allergy:
            alerts.append({"type": "BLOCK", "msg": f"⛔ ALERGIA: Paciente alérgico a {list(match_allergy)}."})

        # --- CAMADA 3: CONTRAINDICAÇÕES ---
        drug_contras = set(drug['contra_indicacoes'])
        match_conditions = drug_contras.intersection(conditions)
        if match_conditions:
            alerts.append({"type": "BLOCK", "msg": f"⛔ CONTRAINDICAÇÃO: Incompatível com {list(match_conditions)}."})

        # --- CAMADA 4: DUPLICIDADE ---
        existing_classes = set()
        for med_id in current_meds_ids:
            m = self.repo.get_drug(med_id)
            if m: existing_classes.add(m['classe_terapeutica'])
        
        if drug['classe_terapeutica'] in existing_classes:
             alerts.append({"type": "WARNING", "msg": f"⚠️ DUPLICIDADE: Já usa fármaco da classe '{drug['classe_terapeutica']}'."})

        # --- CAMADA 5: INTERAÇÕES ---
        active_principles = {drug['principio_ativo']}
        for med_id in current_meds_ids:
            m = self.repo.get_drug(med_id)
            if m: active_principles.add(m['principio_ativo'])
        
        interaction_msgs = self.repo.check_interaction(active_principles)
        for msg in interaction_msgs:
            alerts.append({"type": "BLOCK" if "🔴" in msg else "WARNING", "msg": msg})

        # --- CAMADA 6: POSOLOGIA (CÁLCULO) ---
        is_child = age_months < 144
        ped_rule = drug.get('pediatria')

        if is_child and ped_rule:
            min_dose = weight * ped_rule['min']
            max_dose = weight * ped_rule['max']
            calculated_val = 0.0
            
            if ped_rule['modo'] == 'mg_kg_dose':
                calculated_val = dose_mg
                label = "Dose Unitária"
                # Teto Absoluto
                if 'teto_dose' in ped_rule and calculated_val > ped_rule['teto_dose']:
                    alerts.append({"type": "BLOCK", "msg": f"⛔ TETO ABSOLUTO EXCEDIDO: {calculated_val:.1f}mg > {ped_rule['teto_dose']}mg."})
            else:
                doses_per_day = 24 / freq
                calculated_val = dose_mg * doses_per_day
                label = "Dose Diária Total"

            if calculated_val < min_dose:
                alerts.append({"type": "WARNING", "msg": f"⚠️ SUBDOSE ({label}): {calculated_val:.0f}mg. Mínimo: {min_dose:.0f}mg."})
            elif calculated_val > max_dose:
                # Se for Adrenalina e passar muito, alerta especial
                alerts.append({"type": "BLOCK", "msg": f"⛔ SOBREDOSE TÓXICA ({label}): {calculated_val:.1f}mg. Máximo seguro: {max_dose:.1f}mg."})
        else:
            # Adulto
            doses_per_day = 24 / freq
            total_daily = dose_mg * doses_per_day
            if total_daily > drug['dose_max_diaria_adulto_mg']:
                 alerts.append({"type": "BLOCK", "msg": f"⛔ DOSE DIÁRIA EXCEDIDA: {total_daily:.0f}mg > {drug['dose_max_diaria_adulto_mg']}mg."})
    
        # --- CAMADA 7: VIA DE ADMINISTRAÇÃO ---
        if route not in drug['vias_permitidas']:
            alerts.append({"type": "BLOCK", "msg": f"⛔ ERRO DE VIA: {drug['nome']} não permite via {route}. Use: {drug['vias_permitidas']}."})
        
        return alerts
    
# ==============================================================================
# 3. INTERFACE COMPLETA (RESTAURADA)
# ==============================================================================

def main():
    st.set_page_config(page_title="ValidRx Master", layout="wide", page_icon="🛡️")
    
    repo = DrugRepository()
    engine = ClinicalEngine(repo)

    st.title("🛡️ ValidRx")
    st.markdown("O ValidRx é um mecanismo inteligente de supervisão clínica que valida prescrições em tempo real, prevenindo erros fatais de dosagem, interações medicamentosas e vias de administração")

    # --- SIDEBAR (Completa novamente) ---
    with st.sidebar:
        st.header("📋 Prontuário Eletrônico")
        
        weight = st.number_input("Peso (kg)", 2.0, 150.0, 20.0, 0.5)
        age_years = st.number_input("Idade (Anos)", 0, 100, 6)
        age_months_rem = st.number_input("Meses", 0, 11, 0)
        total_months = (age_years * 12) + age_months_rem
        
        st.subheader("Condições Clínicas")
        conditions = []
        # Adicionei Parada Cardíaca para permitir teste da Adrenalina
        if st.checkbox("Paciente em Parada Cardíaca"): conditions.append("parada_cardiaca")
        if st.checkbox("Insuficiência Renal"): conditions.append("insuficiencia_renal")
        if st.checkbox("Dengue / Suspeita"): conditions.append("dengue")
        if st.checkbox("Gastrite / Úlcera"): conditions.append("gastrite")

        st.subheader("Alergias")
        allergies = []
        if st.checkbox("Alergia a Penicilina"): allergies.append("penicilina")
        if st.checkbox("Alergia a AINEs"): allergies.append("aines")

        st.subheader("Em Uso Contínuo (Interação)")
        current_meds_names = st.multiselect(
            "Medicamentos já em uso:",
            options=["Varfarina 5mg", "Diclofenaco Potássico 50mg"],
            default=[]
        )
        name_to_id = repo.get_all_drugs_list()
        current_meds_ids = [name_to_id[name] for name in current_meds_names]

    # --- MAIN FORM ---
    col_input, col_output = st.columns([1, 1])

    with col_input:
        st.subheader("✍️ Nova Prescrição")
        with st.form("rx_form"):
            drug_name = st.selectbox("Medicamento", list(name_to_id.keys()))
            drug_id = name_to_id[drug_name]
            
            drug_details = repo.get_drug(drug_id)
            
            # Info Contextual
            if drug_details['concentracao_mg_ml']:
                st.info(f"🧪 Líquido: {drug_details['concentracao_mg_ml']} mg/mL")
                dose_input = st.number_input("Dose (mL)", 0.1, 100.0, 5.0, 0.1)
            else:
                st.info("💊 Comprimido (Dose Fixa)")
                dose_input = st.number_input("Dose (mg)", 1.0, 1000.0, 50.0)

            # Nova Camada: Via
            route = st.selectbox("Via de Administração", ["Oral", "Endovenosa (IV)", "Intramuscular (IM)", "Subcutânea"])
            
            freq = st.selectbox("Frequência", [6, 8, 12, 24, "Dose Única"])
            freq_val = 24 if freq == "Dose Única" else freq
            
            submit = st.form_submit_button("🔍 Validar Tudo")

    # --- RESULTADOS ---
    with col_output:
        if submit:
            patient = {
                "weight_kg": weight, "age_months": total_months,
                "conditions": conditions, "allergies": allergies,
                "current_meds": current_meds_ids
            }
            prescription = {
                "drug_id": drug_id, "dose_input": dose_input,
                "freq_hours": freq_val, "route": route
            }

            results = engine.validate_prescription(patient, prescription)

            st.subheader("Relatório de Segurança")
            if not results:
                st.success("✅ Prescrição Segura!")
            else:
                st.error("⚠️ Problemas Encontrados:")
                for alert in results:
                    if alert['type'] == 'BLOCK':
                        st.markdown(f"❌ **BLOQUEANTE:** {alert['msg']}")
                    elif alert['type'] == 'WARNING':
                        st.markdown(f"⚠️ **ALERTA:** {alert['msg']}")

if __name__ == "__main__":
    main()