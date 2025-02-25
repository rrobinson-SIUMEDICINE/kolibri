<template>

  <CoreFullscreen
    ref="slideshowRenderer"
    class="slideshow-renderer"
    :style="{ height: contentHeight }"
    @changeFullscreen="isInFullscreen = $event"
  >
    <UiIconButton
      class="btn"
      :ariaLabel="isInFullscreen ? $tr('exitFullscreen') : $tr('enterFullscreen')"
      color="primary"
      size="small"
      @click="$refs.slideshowRenderer.toggleFullscreen()"
    >
      <mat-svg v-if="isInFullscreen" name="fullscreen_exit" category="navigation" />
      <mat-svg v-else name="fullscreen" category="navigation" />
    </UiIconButton>
    <Hooper v-if="slides" @slide="handleSlide" @loaded="initializeHooper">
      <Slide v-for="slide in slides" :key="slide.id">
        <div
          class="slideshow-slide-image-wrapper"
          :style="{
            height: `calc(100% - ${captionHeight}px)`
          }"
        >
          <img
            :src="slide.storage_url"
            :aria-labelledby="slideTextId(slide.id)"
            class="slideshow-slide-image"
          >
        </div>
        <div :id="slideTextId(slide.id)" class="visuallyhidden">
          {{ slide.descriptive_text || slide.caption }}
        </div>
        <div :ref="slide.id" class="caption">
          {{ slide.caption }}
        </div>
      </Slide>
      <HooperNavigation
        slot="hooper-addons"
        :class="{'hooper-navigation-fullscreen' : isInFullscreen}"
      />
      <HooperPagination slot="hooper-addons" />
    </Hooper>
  </CoreFullscreen>

</template>


<script>

  import orderBy from 'lodash/orderBy';
  import objectFitImages from 'object-fit-images';
  import client from 'kolibri.client';

  import contentRendererMixin from 'kolibri.coreVue.mixins.contentRendererMixin';
  import responsiveElementMixin from 'kolibri.coreVue.mixins.responsiveElementMixin';
  import responsiveWindowMixin from 'kolibri.coreVue.mixins.responsiveWindowMixin';

  import UiIconButton from 'kolibri.coreVue.components.UiIconButton';
  import CoreFullscreen from 'kolibri.coreVue.components.CoreFullscreen';
  import {
    Hooper,
    Slide,
    Navigation as HooperNavigation,
    Pagination as HooperPagination,
  } from 'hooper';
  import { checksumFromFile } from '../utils.js';

  const presets = {
    slideshow_manifest: 'Slideshow Manifest',
  };

  export default {
    name: 'SlideshowRendererComponent',
    components: {
      UiIconButton,
      CoreFullscreen,
      Hooper,
      Slide,
      HooperPagination,
      HooperNavigation,
    },
    mixins: [contentRendererMixin, responsiveElementMixin, responsiveWindowMixin],
    props: {
      defaultFile: {
        type: Object,
        default: () => {},
        validator(file) {
          // File must have a storage_url
          if (file.hasOwnProperty('storage_url')) {
            // Ensure the file is a JSON file because the defaultFile is the manifest.
            return /json$/.test(file.storage_url);
          } else {
            return false;
          }
        },
      },
      files: {
        type: Array,
        default: () => [],
        validator(files) {
          let isValid = true;
          // Ensure we receive a non-empty array.
          if (files.length === 0) {
            return false;
          } else {
            // Check each file to have a storage_url
            files.forEach(file => {
              if (!file.hasOwnProperty('storage_url')) {
                isValid = false;
              }
            });
          }
          return isValid;
        },
      },
    },
    data: () => ({
      isInFullscreen: false,
      manifest: {},
      slides: null,
      currentSlide: null,
    }),
    computed: {
      slideshowImages: function() {
        const files = this.files;
        return files.filter(file => file.preset != presets.slideshow_manifest);
      },
      captionHeight: function() {
        return 30 + (this.currentSlide ? this.$refs[this.currentSlide.id][0].clientHeight : 0);
      },
      contentHeight: function() {
        return window.innerHeight * 0.7 + 'px';
      },
    },
    mounted() {
      /*
        Using the manifest file, get the JSON from the manifest, then
        use the manifest JSON to get all slide images and metadata.
      */
      const path = this.defaultFile.storage_url;
      const method = 'GET';
      client({ path, method }).then(({ entity }) => {
        this.manifest = entity.slideshow_data;

        this.slides = orderBy(
          this.manifest.map(image => {
            return {
              storage_url: this.slideshowImages.find(
                sFile => checksumFromFile(sFile) == image.checksum
              ).storage_url,
              caption: image.caption,
              sort_order: image.sort_order,
              id: image.checksum,
              descriptive_text: image.descriptive_text,
            };
          }),
          ['sort_order'],
          ['asc']
        );
      });
    },
    methods: {
      handleSlide(payload) {
        this.currentSlide = this.slides[payload.currentSlide];
      },
      slideTextId(id) {
        return 'descriptive-text-' + id;
      },
      setHooperListWidth() {
        /*
          Hooper generates a wrapper with the .hooper-list class, which originally uses flexbox.
          In order to implement the same functionality without flexbox, we must use some vanilla JS
          to adjust the width of that element.
        */
        try {
          window.document
            .getElementsByClassName('hooper-list')[0]
            .setAttribute('style', `width: calc(100% * ${this.slides.length});`);
        } catch (err) {
          // If we don't explicitly set an error, the renderer will display broken giving worse
          // UX than getting an error message.
          this.$store.commit('CORE_SET_ERROR', err);
        }
      },
      polyfillSlideObjectFit() {
        /* Instantiate polyfill for object-fit: contain */
        const slideImages = global.window.document.getElementsByClassName('slideshow-slide-image');
        objectFitImages(slideImages);
      },
      initializeHooper() {
        /*
          Hooper emits a "loaded" event. We initialize the object-fit polyfill and set the width of
          the wrapping container for the slides
        */
        this.polyfillSlideObjectFit();
        this.setHooperListWidth();
      },
    },
    $trs: {
      exitFullscreen: 'Exit fullscreen',
      enterFullscreen: 'Enter fullscreen',
    },
  };

</script>


<style lang="scss" scoped>

  @import './custom-hooper.css';

  .btn {
    position: absolute;
    top: 8px;
    right: 8px;
    z-index: 12;
    fill: white;
  }

  .slideshow-renderer {
    position: relative;
    overflow: hidden;
    text-align: center;
  }

  .slideshow-slide-image-wrapper {
    position: relative;
    box-sizing: content-box;
    width: calc(100% - 100px);
    height: calc(100% - 50px);
    margin: 0 auto;
  }

  .slideshow-slide-image {
    width: 100%;
    height: 100%;
    // Adds support for object-fit-images polyfill.
    font-family: 'object-fit: contain;';
    object-fit: contain;
  }

  .hooper {
    height: 100%;
  }

  .hooper-pagination {
    width: 100%;
    background: #cccccc;
  }

  .caption {
    position: absolute;
    bottom: 30px;
    width: 100%;
    padding: 12px;
    background: #efefef;
  }

</style>
