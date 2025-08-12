class DatabaseQueries:
    """데이터베이스 쿼리 모음"""
    
    # 에이전트 instruction 조회 (app_name 기반)
    GET_AGENT_INSTRUCTION = """
        SELECT ai.instruction_content
        FROM service_agent_mappings sam
        JOIN services s ON sam.service_id = s.service_id
        JOIN agents a ON sam.agent_id = a.agent_id
        LEFT JOIN agent_instructions ai ON sam.agent_instruction_id = ai.instruction_id
        WHERE a.name IN (%s, %s)
          AND s.name = %s
          AND sam.is_active = 1;
    """
    
    # 에이전트 카드 정보 조회
    GET_AGENT_CARD = """
        SELECT * FROM agents WHERE name IN (%s, %s) LIMIT 1
    """
    
    # 에이전트 URL 목록 조회 (discovery용)
    GET_AGENT_URLS = """
        SELECT DISTINCT a.base_url, a.agent_id
        FROM service_agent_mappings sam
        INNER JOIN agents a ON sam.agent_id = a.agent_id
        WHERE sam.service_id = %s AND sam.is_active = 1 AND a.is_orchestrator = 0
        ORDER BY a.agent_id ASC
    """
    
    # 에이전트 capabilities 조회
    GET_AGENT_CAPABILITIES = """
        SELECT capabilities FROM agents WHERE name IN (%s, %s) LIMIT 1
    """
    
    # 에이전트 skills 조회
    GET_AGENT_SKILLS = """
        SELECT skills FROM agents WHERE name IN (%s, %s) LIMIT 1
    """
    
    # 에이전트 input/output modes 조회
    GET_AGENT_MODES = """
        SELECT default_input_modes, default_output_modes 
        FROM agents WHERE name IN (%s, %s) LIMIT 1
    """ 