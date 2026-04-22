<script>
  var element = {{Click Element}};
  var getClean = {{JS - Function - Format LowerCase}};
  var getClickText = {{JS - Click Text - Btn and A}};
  var getTextClose = {{JS - Function - Get Text Close}};

  var eventData = {
    activo: "bancolombia",
    seccion: "pagos"
    
  }
  
  function setDataEvent(data, e, cText, clean, getText) {
    if(e.closest('.containerBtnBanner a')) {
        // ----------------------------------------------------------------- Clic Boton Descarga la App
        data['elemento'] = cText;
        data['flujo'] = "apple pay";
        data['ubicacion'] = "banner principal";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Boton', data)};
        return;
    }  else if(e.closest('.card-razon-beneficio-vivienda .contenido-card-razon-beneficio-vivienda')) {
        // --------------------------------------------------------------- Clic Card Beneficios
        data['elemento'] = cText;
        data['flujo'] = "apple pay";
        data['ubicacion'] = "beneficios";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Card', data)};
        return;
    }  else if(e.closest('.contenedor-buttons-tabs .swiper .swiper-wrapper .swiper-slide')) {
        // --------------------------------------------------------------- Clic Boton Inscribir Tarjetas...............
        data['elemento'] = cText;
        data['flujo'] = "billetera de google";
        data['ubicacion'] = "inscribir tus tarjetas";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Boton', data)};
        return;
    } else if(e.closest('.contenido-preguntas-frecuentes .acordeon-pregunta-frecuente')) {
        // --------------------------------------------------------------- Clic Tap Preguntas Frecuentes
        data['elemento'] = cText;
        data['flujo'] = "apple pay";
        data['ubicacion'] = "te perdiste algo";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Tap', data)};
        return;
    } else if(e.closest('.descripcion-alerta-color p strong')) {
        // --------------------------------------------------------------- Clic Link Documento PDF
        data['elemento'] = cText;
        data['flujo'] = "apple pay";
        data['ubicacion'] = "terminos  y condiciones";
    
        if (document.location.href.search('appspot.com') == -1) {analytics.track('Clic Link', data)};
        return;
    }
  }

  setDataEvent(eventData, element, getClickText, getClean, getTextClose);
</script>